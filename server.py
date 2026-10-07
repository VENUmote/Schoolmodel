import getpass
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import sys
import threading
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("SCHOOL_DATABASE", ROOT / "school.db"))
PORT = int(os.environ.get("PORT", "8000"))
SESSION_COOKIE = "sage_staff_session"
BUS_PARENT_SESSION_COOKIE = "sage_bus_parent_session"
SESSION_LIFETIME = timedelta(hours=8)
BUS_LOCATION_MAX_AGE = timedelta(seconds=90)
STAFF_PASSWORD_ITERATIONS = 600_000
STAFF_PASSWORD_MIN_LENGTH = 12
STAFF_PASSWORD_DUMMY_SALT = b"sage-staff-login"
STUDENT_CLASSES = ("Nursery", "LKG", "UKG") + tuple(
    f"Class {grade}" for grade in range(1, 10)
)
STUDENT_HOUSES = ("Red", "Blue", "Yellow", "Green")
DEMO_STUDENTS = (
    ("SAGE-2025-014", "Aarav Mehta", "Class 8", "Current student", None),
    ("SAGE-2023-008", "Diya Rao", "Class 10", "Alumni", 2023),
)
ALUMNI_BATCHES = (
    (2019, 15),
    (2020, 30),
    (2021, 45),
    (2022, 45),
    (2023, 50),
    (2024, 60),
    (2025, 60),
    (2026, 60),
)
DEFAULT_FEES = (
    ("tuition-early", "tuition", "Early years", "Nursery – UKG", 24000, "Learning & activities", 1),
    ("tuition-primary", "tuition", "Primary", "Classes 1 – 5", 32000, "Learning & activities", 2),
    ("tuition-middle", "tuition", "Middle school", "Classes 6 – 8", 42000, "Learning & activities", 3),
    ("tuition-secondary", "tuition", "Secondary", "Classes 9 – 10", 54000, "Learning & activities", 4),
    ("bus-near", "transport", "Near", "0–3 km", 9000, "Optional annual bus transport · sample", 1),
    ("bus-mid", "transport", "Mid", "3–7 km", 15000, "Optional annual bus transport · sample", 2),
    ("bus-far", "transport", "Far", "7+ km", 21000, "Optional annual bus transport · sample", 3),
)
DEFAULT_ACHIEVEMENTS = (
    ("cricket", "Backed the team. Made the play.", "Class 7", "SAMPLE · TEAM SPIRIT"),
    ("football", "Made the pass. Set up a goal.", "Class 6", "SAMPLE · TEAM PARTICIPATION"),
    ("volleyball", "Showed up. Set someone up.", "Class 8", "SAMPLE · TEAM PLAYER"),
    ("badminton", "First match. All heart.", "Class 5", "SAMPLE · PARTICIPATION"),
)
STUDENT_CLASS_CODES = {
    "Nursery": "NUR",
    "LKG": "LKG",
    "UKG": "UKG",
    **{f"Class {grade}": f"{grade:02}" for grade in range(1, 10)},
}
STATIC_FILES = {
    "index.html",
    "manifest.webmanifest",
    "service-worker.js",
    "sage-app-icon-192.png",
    "sage-app-icon-512.png",
    "styles.css",
    "app.js",
    "sage-logo.svg",
    "sage-school-life.jpg",
    "sage-sports-day.jpg",
    "sage-independence-day.jpg",
    "sage-playground.jpg",
    "creative-studio.svg",
    "creative-studio-photo.jpg",
    "garden-club.svg",
    "garden-club-photo.jpg",
    "static-demo.css",
    "static-demo.js",
    "sport-cricket.jpg",
    "sport-football.jpg",
    "sport-volleyball.jpg",
    "sport-tennis.jpg",
    "sport-badminton.jpg",
    "sport-chess.jpg",
    "sport-carrom.jpg",
    "sport-scrabble.jpg",
    "sport-table-tennis.jpg",
}
staff_sessions = {}
parent_sessions = {}
staff_sessions_lock = threading.Lock()


class EnrollmentError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message
        super().__init__(message)


def connect_database():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect_database()) as connection, connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('Current student', 'Alumni')),
                graduation_year INTEGER,
                house TEXT CHECK (house IS NULL OR house IN ('Red', 'Blue', 'Yellow', 'Green'))
            );
            CREATE TABLE IF NOT EXISTS alumni_batches (
                year INTEGER PRIMARY KEY,
                graduates INTEGER NOT NULL CHECK (graduates >= 0)
            );
            CREATE TABLE IF NOT EXISTS student_enrollments (
                enrollment_id INTEGER PRIMARY KEY,
                student_name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                roll_number INTEGER NOT NULL CHECK (roll_number BETWEEN 1 AND 60),
                student_id TEXT UNIQUE,
                house TEXT CHECK (house IS NULL OR house IN ('Red', 'Blue', 'Yellow', 'Green')),
                created_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                ),
                UNIQUE (academic_year, class_name, roll_number)
            );
            CREATE TABLE IF NOT EXISTS bus_location (
                bus_id INTEGER PRIMARY KEY CHECK (bus_id = 1),
                latitude REAL NOT NULL CHECK (latitude BETWEEN -90 AND 90),
                longitude REAL NOT NULL CHECK (longitude BETWEEN -180 AND 180),
                accuracy REAL NOT NULL CHECK (accuracy BETWEEN 0 AND 10000),
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS staff_users (
                username TEXT PRIMARY KEY COLLATE NOCASE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                )
            );
            CREATE TABLE IF NOT EXISTS fee_schedule (
                fee_id TEXT PRIMARY KEY,
                category TEXT NOT NULL CHECK (category IN ('tuition', 'transport')),
                name TEXT NOT NULL,
                band TEXT NOT NULL,
                amount INTEGER NOT NULL CHECK (amount BETWEEN 0 AND 10000000),
                description TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                is_confirmed INTEGER NOT NULL DEFAULT 0
                    CHECK (is_confirmed IN (0, 1))
            );
            CREATE TABLE IF NOT EXISTS achievements (
                achievement_id INTEGER PRIMARY KEY,
                sport TEXT NOT NULL,
                title TEXT NOT NULL,
                class_name TEXT NOT NULL,
                award TEXT NOT NULL,
                is_sample INTEGER NOT NULL DEFAULT 1
                    CHECK (is_sample IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                )
            );
            CREATE TABLE IF NOT EXISTS school_updates (
                update_id INTEGER PRIMARY KEY,
                update_type TEXT NOT NULL CHECK (update_type IN ('notice', 'event')),
                title TEXT NOT NULL,
                details TEXT NOT NULL,
                event_date TEXT,
                created_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                ),
                CHECK (
                    (update_type = 'notice' AND event_date IS NULL)
                    OR (update_type = 'event' AND event_date IS NOT NULL)
                )
            );
            """
        )
        enrollment_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(student_enrollments)")
        }
        if "student_id" not in enrollment_columns:
            connection.execute(
                "ALTER TABLE student_enrollments ADD COLUMN student_id TEXT"
            )
        if "house" not in enrollment_columns:
            connection.execute(
                """
                ALTER TABLE student_enrollments
                ADD COLUMN house TEXT
                    CHECK (house IS NULL OR house IN ('Red', 'Blue', 'Yellow', 'Green'))
                """
            )
        student_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(students)")
        }
        if "house" not in student_columns:
            connection.execute(
                """
                ALTER TABLE students
                ADD COLUMN house TEXT
                    CHECK (house IS NULL OR house IN ('Red', 'Blue', 'Yellow', 'Green'))
                """
            )
        connection.executemany(
            """
            INSERT OR IGNORE INTO students
                (student_id, name, class_name, status, graduation_year)
            VALUES (?, ?, ?, ?, ?)
            """,
            DEMO_STUDENTS,
        )
        connection.executemany(
            """
            INSERT INTO alumni_batches (year, graduates)
            VALUES (?, ?)
            ON CONFLICT(year) DO UPDATE SET graduates = excluded.graduates
            """,
            ALUMNI_BATCHES,
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO fee_schedule
                (fee_id, category, name, band, amount, description, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            DEFAULT_FEES,
        )
        connection.executemany(
            """
            INSERT INTO achievements (sport, title, class_name, award)
            SELECT ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM achievements WHERE sport = ? AND is_sample = 1
            )
            """,
            [
                (*achievement, achievement[0])
                for achievement in DEFAULT_ACHIEVEMENTS
            ],
        )
        migrate_student_enrollments(connection)
    bootstrap_staff_user()


def student_id_for(academic_year, class_name, roll_number):
    starting_year = academic_year.split("-", 1)[0]
    return f"SAGE-{starting_year}-{STUDENT_CLASS_CODES[class_name]}-{roll_number:03}"


def migrate_student_enrollments(connection):
    rows = connection.execute(
        """
        SELECT enrollment_id, student_name, class_name, academic_year, roll_number,
               student_id, house
        FROM student_enrollments
        """
    ).fetchall()
    for row in rows:
        student_id = row["student_id"] or student_id_for(
            row["academic_year"], row["class_name"], row["roll_number"]
        )
        existing_student = connection.execute(
            "SELECT house FROM students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        house = row["house"] or (
            existing_student["house"] if existing_student else None
        )
        connection.execute(
            "UPDATE student_enrollments SET student_id = ? WHERE enrollment_id = ?",
            (student_id, row["enrollment_id"]),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO students
                (student_id, name, class_name, status, graduation_year, house)
            VALUES (?, ?, ?, 'Current student', NULL, ?)
            """,
            (student_id, row["student_name"], row["class_name"], house),
        )
        connection.execute(
            "UPDATE student_enrollments SET house = ? WHERE enrollment_id = ?",
            (house, row["enrollment_id"]),
        )
        connection.execute(
            "UPDATE students SET house = ? WHERE student_id = ?",
            (house, student_id),
        )


def hash_staff_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        STAFF_PASSWORD_ITERATIONS,
    )


def create_staff_user(username, password):
    if not isinstance(username, str) or not isinstance(password, str):
        raise ValueError("Enter a staff username and password.")
    username = username.strip()
    if not username or len(username) > 100:
        raise ValueError("The staff username must contain 1 to 100 characters.")
    if any(ord(character) < 32 for character in username):
        raise ValueError("The staff username contains an unsupported character.")
    if len(password) < STAFF_PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Staff passwords must be at least {STAFF_PASSWORD_MIN_LENGTH} characters."
        )

    salt = secrets.token_bytes(16)
    password_hash = hash_staff_password(password, salt)
    with closing(connect_database()) as connection, connection:
        try:
            connection.execute(
                """
                INSERT INTO staff_users (username, password_salt, password_hash)
                VALUES (?, ?, ?)
                """,
                (username, salt.hex(), password_hash.hex()),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("That staff username already exists.") from error


def bootstrap_staff_user():
    username = os.environ.get("SAGE_ADMIN_USERNAME", "")
    password = os.environ.get("SAGE_ADMIN_PASSWORD", "")
    if not username or not password:
        return

    with closing(connect_database()) as connection:
        existing_user = connection.execute(
            "SELECT 1 FROM staff_users LIMIT 1"
        ).fetchone()
    if existing_user:
        return

    try:
        create_staff_user(username, password)
    except ValueError as error:
        raise RuntimeError(f"Could not create the initial staff account: {error}") from error


def staff_is_configured():
    with closing(connect_database()) as connection:
        return connection.execute(
            "SELECT 1 FROM staff_users LIMIT 1"
        ).fetchone() is not None


def authenticate_staff(username, password):
    if not isinstance(username, str) or not isinstance(password, str):
        return False
    with closing(connect_database()) as connection:
        row = connection.execute(
            """
            SELECT password_salt, password_hash
            FROM staff_users WHERE username = ?
            """,
            (username.strip(),),
        ).fetchone()

    if row is None:
        candidate_hash = hash_staff_password(password, STAFF_PASSWORD_DUMMY_SALT)
        hmac.compare_digest(candidate_hash, bytes(32))
        return False

    salt = bytes.fromhex(row["password_salt"])
    expected_hash = bytes.fromhex(row["password_hash"])
    actual_hash = hash_staff_password(password, salt)
    return hmac.compare_digest(actual_hash, expected_hash)


def get_student(student_id):
    with closing(connect_database()) as connection:
        row = connection.execute(
            """
            SELECT student_id, name, class_name, status, graduation_year
            FROM students
            WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
    return dict(row) if row else None


def get_alumni_batches():
    with closing(connect_database()) as connection:
        rows = connection.execute(
            "SELECT year, graduates FROM alumni_batches ORDER BY year"
        ).fetchall()
    batches = [dict(row) for row in rows]
    return {
        "batches": batches,
        "totalGraduates": sum(batch["graduates"] for batch in batches),
    }


def get_fee_schedule():
    with closing(connect_database()) as connection:
        rows = connection.execute(
            """
            SELECT fee_id, category, name, band, amount, description, sort_order,
                   is_confirmed
            FROM fee_schedule
            ORDER BY category, sort_order
            """
        ).fetchall()
    return [
        {
            "feeId": row["fee_id"],
            "category": row["category"],
            "name": row["name"],
            "band": row["band"],
            "amount": row["amount"],
            "description": row["description"],
            "sortOrder": row["sort_order"],
            "isConfirmed": bool(row["is_confirmed"]),
        }
        for row in rows
    ]


def update_fee_schedule(fee_id, amount, is_confirmed):
    if not isinstance(fee_id, str):
        raise EnrollmentError(400, "Choose a valid school fee.")
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise EnrollmentError(400, "Enter a whole-number fee amount in rupees.")
    if not 0 <= amount <= 10_000_000:
        raise EnrollmentError(400, "Fee amounts must be between ₹0 and ₹10,000,000.")
    if not isinstance(is_confirmed, bool):
        raise EnrollmentError(400, "Choose whether the school has confirmed this fee.")
    with closing(connect_database()) as connection, connection:
        cursor = connection.execute(
            """
            UPDATE fee_schedule SET amount = ?, is_confirmed = ?
            WHERE fee_id = ?
            """,
            (amount, int(is_confirmed), fee_id),
        )
        if cursor.rowcount != 1:
            raise EnrollmentError(404, "That school fee could not be found.")
    return next(fee for fee in get_fee_schedule() if fee["feeId"] == fee_id)


def get_achievements():
    with closing(connect_database()) as connection:
        rows = connection.execute(
            """
            SELECT achievement_id, sport, title, class_name, award, is_sample
            FROM achievements
            ORDER BY created_at DESC, achievement_id DESC
            """
        ).fetchall()
    return [
        {
            "achievementId": row["achievement_id"],
            "sport": row["sport"],
            "title": row["title"],
            "className": row["class_name"],
            "award": row["award"],
            "isSample": bool(row["is_sample"]),
        }
        for row in rows
    ]


def create_achievement(sport, title, class_name, award):
    sports = {
        "cricket", "football", "volleyball", "tennis", "badminton",
        "chess", "carrom", "scrabble", "table-tennis",
    }
    if not isinstance(sport, str) or sport not in sports:
        raise EnrollmentError(400, "Choose one of the listed school activities.")
    if class_name not in (*STUDENT_CLASSES, "Class 10"):
        raise EnrollmentError(400, "Choose Nursery through Class 10.")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 160:
        raise EnrollmentError(400, "Enter a highlight between 1 and 160 characters.")
    if not isinstance(award, str) or not award.strip() or len(award.strip()) > 80:
        raise EnrollmentError(400, "Enter an award label between 1 and 80 characters.")
    with closing(connect_database()) as connection, connection:
        cursor = connection.execute(
            """
            INSERT INTO achievements
                (sport, title, class_name, award, is_sample)
            VALUES (?, ?, ?, ?, 0)
            """,
            (sport, title.strip(), class_name, award.strip()),
        )
        achievement_id = cursor.lastrowid
    return next(
        achievement
        for achievement in get_achievements()
        if achievement["achievementId"] == achievement_id
    )


def delete_achievement(achievement_id):
    if isinstance(achievement_id, bool) or not isinstance(achievement_id, int):
        raise EnrollmentError(400, "Choose a valid achievement to remove.")
    with closing(connect_database()) as connection, connection:
        cursor = connection.execute(
            "DELETE FROM achievements WHERE achievement_id = ? AND is_sample = 0",
            (achievement_id,),
        )
    if cursor.rowcount != 1:
        raise EnrollmentError(404, "That school achievement could not be found.")


def get_school_updates(today=None):
    today = today or date.today()
    with closing(connect_database()) as connection:
        rows = connection.execute(
            """
            SELECT update_id, update_type, title, details, event_date
            FROM school_updates
            WHERE update_type = 'notice' OR event_date >= ?
            ORDER BY
                CASE WHEN update_type = 'notice' THEN 0 ELSE 1 END,
                event_date ASC,
                created_at DESC,
                update_id DESC
            LIMIT 12
            """,
            (today.isoformat(),),
        ).fetchall()
    return [
        {
            "updateId": row["update_id"],
            "type": row["update_type"],
            "title": row["title"],
            "details": row["details"],
            "date": row["event_date"],
        }
        for row in rows
    ]


def create_school_update(update_type, title, details, event_date):
    if not isinstance(update_type, str) or update_type not in {"notice", "event"}:
        raise EnrollmentError(400, "Choose a notice or event.")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 120:
        raise EnrollmentError(400, "Enter a title between 1 and 120 characters.")
    if not isinstance(details, str) or not details.strip() or len(details.strip()) > 600:
        raise EnrollmentError(400, "Enter details between 1 and 600 characters.")
    if update_type == "event":
        if not isinstance(event_date, str):
            raise EnrollmentError(400, "Choose a date for this event.")
        try:
            parsed_date = datetime.strptime(event_date, "%Y-%m-%d").date()
        except ValueError as error:
            raise EnrollmentError(400, "Choose a valid event date.") from error
        if parsed_date.isoformat() != event_date:
            raise EnrollmentError(400, "Choose a valid event date.")
        if parsed_date < date.today():
            raise EnrollmentError(400, "Choose today or a future date for this event.")
    else:
        event_date = None

    with closing(connect_database()) as connection, connection:
        cursor = connection.execute(
            """
            INSERT INTO school_updates (update_type, title, details, event_date)
            VALUES (?, ?, ?, ?)
            """,
            (update_type, title.strip(), details.strip(), event_date),
        )
        update_id = cursor.lastrowid
        row = connection.execute(
            """
            SELECT update_id, update_type, title, details, event_date
            FROM school_updates WHERE update_id = ?
            """,
            (update_id,),
        ).fetchone()
    return {
        "updateId": row["update_id"],
        "type": row["update_type"],
        "title": row["title"],
        "details": row["details"],
        "date": row["event_date"],
    }


def delete_school_update(update_id):
    if isinstance(update_id, bool) or not isinstance(update_id, int):
        raise EnrollmentError(400, "Choose a valid school update to remove.")
    with closing(connect_database()) as connection, connection:
        cursor = connection.execute(
            "DELETE FROM school_updates WHERE update_id = ?",
            (update_id,),
        )
    if cursor.rowcount != 1:
        raise EnrollmentError(404, "That school update could not be found.")


def save_bus_location(latitude, longitude, accuracy):
    coordinates = (latitude, longitude, accuracy)
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in coordinates
    ):
        raise EnrollmentError(400, "Valid GPS coordinates and accuracy are required.")
    if not all(math.isfinite(value) for value in coordinates):
        raise EnrollmentError(400, "GPS coordinates must be finite numbers.")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise EnrollmentError(400, "GPS coordinates are outside the valid range.")
    if not 0 <= accuracy <= 10000:
        raise EnrollmentError(400, "GPS accuracy must be between 0 and 10,000 metres.")

    updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(connect_database()) as connection, connection:
        connection.execute(
            """
            INSERT INTO bus_location (bus_id, latitude, longitude, accuracy, updated_at)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(bus_id) DO UPDATE SET
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                accuracy = excluded.accuracy,
                updated_at = excluded.updated_at
            """,
            (round(latitude, 6), round(longitude, 6), round(accuracy, 1), updated_at),
        )
    return get_bus_location()


def get_bus_location(now=None):
    with closing(connect_database()) as connection:
        row = connection.execute(
            """
            SELECT latitude, longitude, accuracy, updated_at
            FROM bus_location WHERE bus_id = 1
            """
        ).fetchone()
    if row is None:
        return {"active": False}

    updated_at = datetime.fromisoformat(row["updated_at"])
    now = now or datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age_seconds = max(0, (now - updated_at).total_seconds())
    if age_seconds > BUS_LOCATION_MAX_AGE.total_seconds():
        clear_bus_location()
        return {"active": False}

    return {
        "active": True,
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "accuracy": row["accuracy"],
        "updatedAt": row["updated_at"],
    }


def clear_bus_location():
    with closing(connect_database()) as connection, connection:
        connection.execute("DELETE FROM bus_location WHERE bus_id = 1")


def get_school_years(today=None):
    today = today or datetime.now()
    starting_year = today.year if today.month >= 6 else today.year - 1
    return [
        f"{year}-{str(year + 1)[-2:]}"
        for year in range(starting_year, starting_year + 3)
    ]


def validate_school_year(academic_year):
    if academic_year not in get_school_years():
        raise EnrollmentError(400, "Choose one of the available school years.")
    return academic_year


def enroll_student(student_name, class_name, academic_year, house):
    if not isinstance(student_name, str):
        raise EnrollmentError(400, "Enter a student name.")
    student_name = student_name.strip()
    if not student_name or len(student_name) > 100:
        raise EnrollmentError(400, "Enter a name between 1 and 100 characters.")
    if any(ord(character) < 32 for character in student_name):
        raise EnrollmentError(400, "The name contains an unsupported character.")
    if class_name not in STUDENT_CLASSES:
        raise EnrollmentError(400, "Choose Nursery through Class 9.")
    validate_school_year(academic_year)
    if house not in STUDENT_HOUSES:
        raise EnrollmentError(400, "Choose one of the four school houses.")

    with closing(connect_database()) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            current_max = connection.execute(
                """
                SELECT COALESCE(MAX(roll_number), 0)
                FROM student_enrollments
                WHERE academic_year = ? AND class_name = ?
                """,
                (academic_year, class_name),
            ).fetchone()[0]
            if current_max >= 60:
                raise EnrollmentError(
                    409, f"{class_name} is full for {academic_year} (60 students)."
                )
            roll_number = current_max + 1
            student_id = student_id_for(academic_year, class_name, roll_number)
            connection.execute(
                """
                INSERT INTO student_enrollments
                    (student_name, class_name, academic_year, roll_number, student_id, house)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (student_name, class_name, academic_year, roll_number, student_id, house),
            )
            connection.execute(
                """
                INSERT INTO students
                    (student_id, name, class_name, status, graduation_year, house)
                VALUES (?, ?, ?, 'Current student', NULL, ?)
                """,
                (student_id, student_name, class_name, house),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return {
        "name": student_name,
        "className": class_name,
        "academicYear": academic_year,
        "rollNumber": roll_number,
        "studentId": student_id,
        "house": house,
    }


def get_class_roster(class_name, academic_year):
    if class_name not in STUDENT_CLASSES:
        raise EnrollmentError(400, "Choose Nursery through Class 9.")
    validate_school_year(academic_year)
    with closing(connect_database()) as connection:
        rows = connection.execute(
            """
            SELECT student_name, roll_number, created_at, student_id, house
            FROM student_enrollments
            WHERE academic_year = ? AND class_name = ?
            ORDER BY roll_number
            """,
            (academic_year, class_name),
        ).fetchall()
    return [
        {
            "name": row["student_name"],
            "rollNumber": row["roll_number"],
            "studentId": row["student_id"],
            "createdAt": row["created_at"],
            "house": row["house"],
        }
        for row in rows
    ]


def assign_student_house(student_id, house):
    if not isinstance(student_id, str) or not student_id:
        raise EnrollmentError(400, "Choose a valid enrolled student.")
    if house not in STUDENT_HOUSES:
        raise EnrollmentError(400, "Choose one of the four school houses.")

    with closing(connect_database()) as connection, connection:
        enrollment = connection.execute(
            "SELECT student_id FROM student_enrollments WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        if enrollment is None:
            raise EnrollmentError(404, "That enrolled student could not be found.")
        connection.execute(
            "UPDATE student_enrollments SET house = ? WHERE student_id = ?",
            (house, student_id),
        )
        cursor = connection.execute(
            "UPDATE students SET house = ? WHERE student_id = ?",
            (house, student_id),
        )
        if cursor.rowcount != 1:
            raise EnrollmentError(404, "That student status record could not be found.")
    return {"studentId": student_id, "house": house}


def search_students(query):
    if not isinstance(query, str):
        raise EnrollmentError(400, "Enter a student name, ID, class, or house.")
    query = query.strip()
    if not query or len(query) > 100:
        raise EnrollmentError(400, "Search text must be between 1 and 100 characters.")
    if any(ord(character) < 32 for character in query):
        raise EnrollmentError(400, "Search text contains an unsupported character.")

    student_id_match = re.search(
        r"\bSAGE-\d{4}-(?:NUR|LKG|UKG|\d{2})-\d{3}\b",
        query,
        re.IGNORECASE,
    )
    class_match = re.search(
        r"\b(Nursery|LKG|UKG|Class\s+(?:10|[1-9]))\b",
        query,
        re.IGNORECASE,
    )
    house_match = re.search(
        r"\b(Red|Blue|Yellow|Green)\s*(?:house|team)?\b",
        query,
        re.IGNORECASE,
    )
    unassigned_match = re.search(r"\bunassigned\b", query, re.IGNORECASE)
    student_id = student_id_match.group(0).upper() if student_id_match else None
    class_name = class_match.group(0).title() if class_match else None
    if class_name and class_name.lower().startswith("class "):
        class_name = f"Class {class_name.split()[-1]}"
    elif class_name:
        class_name = class_name.upper() if class_name.upper() in {"LKG", "UKG"} else "Nursery"
    house = house_match.group(1).title() if house_match else None

    name_query = query
    for match in (student_id_match, class_match, house_match, unassigned_match):
        if match:
            name_query = name_query.replace(match.group(0), " ")
    name_terms = [
        word
        for word in re.findall(r"[\w'-]+", name_query, re.UNICODE)
        if word.casefold() not in {
            "find", "search", "look", "up", "show", "list", "me", "please", "by",
            "student", "students", "who", "is", "in", "from", "the", "class",
            "unassigned", "a", "an", "for", "name", "named",
            "id", "details",
        }
    ]
    name_query = " ".join(name_terms)
    if not any((student_id, class_name, house, unassigned_match, name_query)):
        raise EnrollmentError(400, "Try a name, student ID, class, or house.")

    conditions = []
    values = []
    if student_id:
        conditions.append("student_id = ?")
        values.append(student_id)
    if class_name:
        conditions.append("class_name = ?")
        values.append(class_name)
    if house:
        conditions.append("house = ?")
        values.append(house)
    elif unassigned_match:
        conditions.append("house IS NULL")
    if name_query:
        conditions.append("student_name LIKE ? ESCAPE '\\'")
        escaped_name = name_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        values.append(f"%{escaped_name}%")

    with closing(connect_database()) as connection:
        rows = connection.execute(
            f"""
            SELECT student_id, student_name, class_name, academic_year,
                   roll_number, house
            FROM student_enrollments
            WHERE {" AND ".join(conditions)}
            ORDER BY class_name, academic_year DESC, roll_number
            LIMIT 21
            """,
            values,
        ).fetchall()
    return {
        "students": [
            {
                "studentId": row["student_id"],
                "name": row["student_name"],
                "className": row["class_name"],
                "academicYear": row["academic_year"],
                "rollNumber": row["roll_number"],
                "house": row["house"],
            }
            for row in rows[:20]
        ],
        "hasMore": len(rows) > 20,
    }


def create_staff_session():
    token = secrets.token_urlsafe(32)
    expiration = datetime.now() + SESSION_LIFETIME
    with staff_sessions_lock:
        for expired_token in [
            session_token
            for session_token, expires_at in staff_sessions.items()
            if expires_at <= datetime.now()
        ]:
            del staff_sessions[expired_token]
        staff_sessions[token] = expiration
    return token


def is_authenticated_staff(cookie_header):
    cookies = {}
    for item in cookie_header.split(";"):
        name, separator, value = item.strip().partition("=")
        if separator:
            cookies[name] = value
    token = cookies.get(SESSION_COOKIE)
    if not token:
        return False

    now = datetime.now()
    with staff_sessions_lock:
        expiration = staff_sessions.get(token)
        if expiration is None:
            return False
        if expiration <= now:
            del staff_sessions[token]
            return False
        staff_sessions[token] = now + SESSION_LIFETIME
    return True


def create_parent_session():
    token = secrets.token_urlsafe(32)
    expiration = datetime.now() + SESSION_LIFETIME
    with staff_sessions_lock:
        now = datetime.now()
        for expired_token in [
            session_token
            for session_token, expires_at in parent_sessions.items()
            if expires_at <= now
        ]:
            del parent_sessions[expired_token]
        parent_sessions[token] = expiration
    return token


def is_authenticated_parent(cookie_header):
    cookies = {}
    for item in cookie_header.split(";"):
        name, separator, value = item.strip().partition("=")
        if separator:
            cookies[name] = value
    token = cookies.get(BUS_PARENT_SESSION_COOKIE)
    if not token:
        return False

    now = datetime.now()
    with staff_sessions_lock:
        expiration = parent_sessions.get(token)
        if expiration is None:
            return False
        if expiration <= now:
            del parent_sessions[token]
            return False
        parent_sessions[token] = now + SESSION_LIFETIME
    return True


class SchoolRequestHandler(BaseHTTPRequestHandler):
    def send_json(self, status, payload, headers=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        request = urlparse(self.path)
        if request.path == "/api/staff/session":
            configured = staff_is_configured()
            self.send_json(
                200,
                {
                    "enabled": configured,
                    "authenticated": configured
                    and is_authenticated_staff(self.headers.get("Cookie", "")),
                    "classes": STUDENT_CLASSES,
                    "houses": STUDENT_HOUSES,
                    "schoolYears": get_school_years(),
                    "capacityPerClass": 60,
                },
            )
            return

        if request.path == "/api/bus/parent/session":
            configured = bool(os.environ.get("SAGE_BUS_VIEWER_CODE"))
            self.send_json(
                200,
                {
                    "enabled": configured,
                    "authenticated": configured
                    and is_authenticated_parent(self.headers.get("Cookie", "")),
                },
            )
            return

        if request.path == "/api/bus/location":
            if not self.require_bus_parent():
                return
            self.send_json(200, get_bus_location())
            return

        if request.path == "/api/staff/roster":
            if not self.require_staff():
                return
            parameters = parse_qs(request.query)
            try:
                class_name = parameters.get("className", [""])[0]
                academic_year = parameters.get("academicYear", [""])[0]
                self.send_json(
                    200,
                    {
                        "className": class_name,
                        "academicYear": academic_year,
                        "students": get_class_roster(class_name, academic_year),
                    },
                )
            except EnrollmentError as error:
                self.send_json(error.status, {"error": error.message})
            return

        if request.path == "/api/staff/student-search":
            if not self.require_staff():
                return
            parameters = parse_qs(request.query)
            try:
                self.send_json(
                    200,
                    search_students(parameters.get("q", [""])[0]),
                )
            except EnrollmentError as error:
                self.send_json(error.status, {"error": error.message})
            return

        if request.path == "/api/student":
            student_id = parse_qs(request.query).get("id", [""])[0].strip()
            if not student_id or len(student_id) > 40:
                self.send_json(400, {"error": "A student ID of 1 to 40 characters is required."})
                return
            student = get_student(student_id)
            if student is None:
                self.send_json(404, {"error": "No demo record found."})
                return
            self.send_json(200, student)
            return

        if request.path == "/api/alumni-batches":
            self.send_json(200, get_alumni_batches())
            return

        if request.path == "/api/fees":
            fees = get_fee_schedule()
            self.send_json(
                200,
                {
                    "fees": fees,
                    "allConfirmed": bool(fees) and all(
                        fee["isConfirmed"] for fee in fees
                    ),
                },
            )
            return

        if request.path == "/api/achievements":
            achievements = get_achievements()
            self.send_json(
                200,
                {
                    "achievements": achievements,
                    "allSample": all(
                        achievement["isSample"] for achievement in achievements
                    ),
                },
            )
            return

        if request.path == "/api/school-updates":
            self.send_json(200, {"updates": get_school_updates()})
            return

        self.serve_static(request.path)

    def do_POST(self):
        request = urlparse(self.path)
        if request.path not in {
            "/api/staff/login",
            "/api/staff/logout",
            "/api/staff/enroll",
            "/api/staff/achievements",
            "/api/staff/school-updates",
            "/api/bus/parent/login",
            "/api/bus/parent/logout",
            "/api/staff/bus-location",
            "/api/staff/bus-location/stop",
        }:
            self.send_json(404, {"error": "Route not found."})
            return
        if not self.require_same_origin():
            return

        if request.path == "/api/staff/login":
            self.login_staff()
            return

        if request.path == "/api/staff/logout":
            self.logout_staff()
            return

        if request.path == "/api/bus/parent/login":
            self.login_bus_parent()
            return

        if request.path == "/api/bus/parent/logout":
            self.logout_bus_parent()
            return

        if not self.require_staff():
            return

        if request.path == "/api/staff/bus-location/stop":
            clear_bus_location()
            self.send_json(200, {"sharing": False})
            return

        payload = self.read_json()
        if payload is None:
            return
        if request.path == "/api/staff/achievements":
            try:
                achievement = create_achievement(
                    payload.get("sport"),
                    payload.get("title"),
                    payload.get("className"),
                    payload.get("award"),
                )
                self.send_json(201, achievement)
            except EnrollmentError as error:
                self.send_json(error.status, {"error": error.message})
            return
        if request.path == "/api/staff/school-updates":
            try:
                update = create_school_update(
                    payload.get("type"),
                    payload.get("title"),
                    payload.get("details"),
                    payload.get("date"),
                )
                self.send_json(201, update)
            except EnrollmentError as error:
                self.send_json(error.status, {"error": error.message})
            return
        if request.path == "/api/staff/bus-location":
            try:
                location = save_bus_location(
                    payload.get("latitude"),
                    payload.get("longitude"),
                    payload.get("accuracy"),
                )
                self.send_json(200, {"sharing": True, **location})
            except EnrollmentError as error:
                self.send_json(error.status, {"error": error.message})
            return

        try:
            enrollment = enroll_student(
                payload.get("name", ""),
                payload.get("className", ""),
                payload.get("academicYear", ""),
                payload.get("house", ""),
            )
            self.send_json(201, enrollment)
        except EnrollmentError as error:
            self.send_json(error.status, {"error": error.message})

    def do_PUT(self):
        request = urlparse(self.path)
        if request.path not in {
            "/api/staff/fees",
            "/api/staff/student-house",
        }:
            self.send_json(404, {"error": "Route not found."})
            return
        if not self.require_same_origin() or not self.require_staff():
            return
        payload = self.read_json()
        if payload is None:
            return
        if request.path == "/api/staff/student-house":
            try:
                student = assign_student_house(
                    payload.get("studentId"),
                    payload.get("house"),
                )
                self.send_json(200, student)
            except EnrollmentError as error:
                self.send_json(error.status, {"error": error.message})
            return
        try:
            fee = update_fee_schedule(
                payload.get("feeId"),
                payload.get("amount"),
                payload.get("isConfirmed"),
            )
            self.send_json(200, fee)
        except EnrollmentError as error:
            self.send_json(error.status, {"error": error.message})

    def do_DELETE(self):
        request = urlparse(self.path)
        if request.path not in {
            "/api/staff/achievements",
            "/api/staff/school-updates",
        }:
            self.send_json(404, {"error": "Route not found."})
            return
        if not self.require_same_origin() or not self.require_staff():
            return
        payload = self.read_json()
        if payload is None:
            return
        if request.path == "/api/staff/school-updates":
            try:
                delete_school_update(payload.get("updateId"))
                self.send_json(200, {"deleted": True})
            except EnrollmentError as error:
                self.send_json(error.status, {"error": error.message})
            return
        try:
            delete_achievement(payload.get("achievementId"))
            self.send_json(200, {"deleted": True})
        except EnrollmentError as error:
            self.send_json(error.status, {"error": error.message})

    def require_same_origin(self):
        origin = self.headers.get("Origin", "")
        public_scheme = os.environ.get("SAGE_PUBLIC_SCHEME", "http")
        if public_scheme not in {"http", "https"}:
            self.send_json(500, {"error": "The public website scheme is invalid."})
            return False
        expected_origin = f"{public_scheme}://{self.headers.get('Host', '')}"
        if origin != expected_origin:
            self.send_json(403, {"error": "Request must come from this school website."})
            return False
        return True

    def require_staff(self):
        if not staff_is_configured():
            self.send_json(
                503, {"error": "Staff enrollment has not been configured."}
            )
            return False
        if not is_authenticated_staff(self.headers.get("Cookie", "")):
            self.send_json(401, {"error": "Sign in to the staff portal first."})
            return False
        return True

    def require_bus_parent(self):
        if not os.environ.get("SAGE_BUS_VIEWER_CODE"):
            self.send_json(
                503, {"error": "Parent bus tracking has not been configured."}
            )
            return False
        if not is_authenticated_parent(self.headers.get("Cookie", "")):
            self.send_json(401, {"error": "Enter the private school bus access code."})
            return False
        return True

    def login_bus_parent(self):
        access_code = os.environ.get("SAGE_BUS_VIEWER_CODE", "")
        if not access_code:
            self.send_json(
                503, {"error": "Parent bus tracking has not been configured."}
            )
            return

        payload = self.read_json()
        if payload is None:
            return
        provided_code = payload.get("accessCode")
        if not isinstance(provided_code, str):
            self.send_json(400, {"error": "Enter the school bus access code."})
            return
        if not hmac.compare_digest(
            provided_code.encode("utf-8"), access_code.encode("utf-8")
        ):
            self.send_json(401, {"error": "The bus access code is incorrect."})
            return

        token = create_parent_session()
        self.send_json(
            200,
            {"authenticated": True},
            {"Set-Cookie": self.session_cookie(
                token, BUS_PARENT_SESSION_COOKIE
            )},
        )

    def logout_bus_parent(self):
        token = self.get_cookie(BUS_PARENT_SESSION_COOKIE)
        if token:
            with staff_sessions_lock:
                parent_sessions.pop(token, None)
        self.send_json(
            200,
            {"authenticated": False},
            {"Set-Cookie": self.session_cookie(
                "", BUS_PARENT_SESSION_COOKIE, max_age=0
            )},
        )

    def get_cookie(self, cookie_name):
        for item in self.headers.get("Cookie", "").split(";"):
            name, separator, value = item.strip().partition("=")
            if separator and name == cookie_name:
                return value
        return ""

    def read_json(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"error": "Invalid request length."})
            return None
        if content_length < 1 or content_length > 4096:
            self.send_json(400, {"error": "Request must be between 1 and 4096 bytes."})
            return None
        if self.headers.get_content_type() != "application/json":
            self.send_json(415, {"error": "Send JSON data to this endpoint."})
            return None
        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json(400, {"error": "Request body must be valid JSON."})
            return None
        if not isinstance(payload, dict):
            self.send_json(400, {"error": "Request body must be a JSON object."})
            return None
        return payload

    def login_staff(self):
        if not staff_is_configured():
            self.send_json(503, {"error": "Staff enrollment has not been configured."})
            return

        payload = self.read_json()
        if payload is None:
            return
        username = payload.get("username")
        password = payload.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            self.send_json(400, {"error": "Enter a username and password."})
            return
        if not authenticate_staff(username, password):
            self.send_json(
                401, {"error": "The staff username or password is incorrect."}
            )
            return

        token = create_staff_session()
        self.send_json(
            200,
            {"authenticated": True},
            {"Set-Cookie": self.session_cookie(token)},
        )

    def logout_staff(self):
        token = self.get_cookie(SESSION_COOKIE)
        if token:
            with staff_sessions_lock:
                staff_sessions.pop(token, None)
        clear_bus_location()
        self.send_json(
            200,
            {"authenticated": False},
            {"Set-Cookie": self.session_cookie("", max_age=0)},
        )

    def session_cookie(
        self,
        token,
        cookie_name=SESSION_COOKIE,
        max_age=SESSION_LIFETIME.total_seconds(),
    ):
        secure_flag = (
            "; Secure" if os.environ.get("SAGE_PUBLIC_SCHEME", "http") == "https" else ""
        )
        return (
            f"{cookie_name}={token}; Path=/; HttpOnly; SameSite=Strict"
            f"{secure_flag}; "
            f"Max-Age={int(max_age)}"
        )

    def serve_static(self, requested_path):
        relative_path = "index.html" if requested_path == "/" else requested_path.lstrip("/")
        if relative_path not in STATIC_FILES:
            self.send_error(404)
            return
        target = (ROOT / relative_path).resolve()
        try:
            target.relative_to(ROOT)
        except ValueError:
            self.send_error(404)
            return
        if not target.is_file():
            self.send_error(404)
            return

        content_type = {
            ".css": "text/css; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".webmanifest": "application/manifest+json; charset=utf-8",
            ".jpg": "image/jpeg",
            ".png": "image/png",
            ".svg": "image/svg+xml",
        }.get(target.suffix, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format_string, *args):
        print(f"{self.address_string()} - {format_string % args}")


def create_staff_from_prompt():
    initialize_database()
    username = input("New staff username: ").strip()
    password = getpass.getpass("New staff password: ")
    confirmation = getpass.getpass("Confirm staff password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match; no account was created.")
    try:
        create_staff_user(username, password)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(f"Staff account {username!r} created in {DATABASE_PATH}.")


def main():
    if sys.argv[1:] == ["--create-staff"]:
        create_staff_from_prompt()
        return

    initialize_database()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), SchoolRequestHandler)
    print(f"Sage High School demo running at http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Sage High School demo.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
