import http.client
import io
import json
import os
import struct
import tempfile
import threading
import unittest
import build_static
from contextlib import closing, redirect_stdout
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

import server


class SchoolServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "school.db"
        with patch.object(server, "DATABASE_PATH", self.database_path):
            server.initialize_database()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_student_lookup_returns_current_student(self):
        with patch.object(server, "DATABASE_PATH", self.database_path):
            student = server.get_student("SAGE-2025-014")
        self.assertEqual(student["status"], "Current student")
        self.assertEqual(student["class_name"], "Class 8")

    def test_student_lookup_returns_alumni(self):
        with patch.object(server, "DATABASE_PATH", self.database_path):
            student = server.get_student("SAGE-2023-008")
        self.assertEqual(student["status"], "Alumni")
        self.assertEqual(student["graduation_year"], 2023)

    def test_unknown_student_is_not_returned(self):
        with patch.object(server, "DATABASE_PATH", self.database_path):
            student = server.get_student("not-a-student")
        self.assertIsNone(student)

    def test_alumni_batch_counts_and_total_match_school_records(self):
        with patch.object(server, "DATABASE_PATH", self.database_path):
            alumni = server.get_alumni_batches()
        self.assertEqual(alumni["batches"], [
            {"year": 2019, "graduates": 15},
            {"year": 2020, "graduates": 30},
            {"year": 2021, "graduates": 45},
            {"year": 2022, "graduates": 45},
            {"year": 2023, "graduates": 50},
            {"year": 2024, "graduates": 60},
            {"year": 2025, "graduates": 60},
            {"year": 2026, "graduates": 60},
        ])
        self.assertEqual(alumni["totalGraduates"], 365)

    def test_alumni_batch_counts_are_refreshed_from_school_records(self):
        with patch.object(server, "DATABASE_PATH", self.database_path):
            with closing(server.connect_database()) as connection, connection:
                connection.execute(
                    "UPDATE alumni_batches SET graduates = 999 WHERE year = 2019"
                )
            server.initialize_database()
            alumni = server.get_alumni_batches()
        self.assertEqual(alumni["batches"][0]["graduates"], 15)

    def test_roll_numbers_start_at_one_and_increment_within_each_class(self):
        school_year = server.get_school_years()[0]
        with patch.object(server, "DATABASE_PATH", self.database_path):
            for class_name in server.STUDENT_CLASSES:
                first = server.enroll_student(
                    "First learner", class_name, school_year, "Red"
                )
                second = server.enroll_student(
                    "Second learner", class_name, school_year, "Blue"
                )
                self.assertEqual(first["rollNumber"], 1, class_name)
                self.assertEqual(second["rollNumber"], 2, class_name)

    def test_roll_numbers_reset_for_a_new_school_year(self):
        school_year = server.get_school_years()[0]
        next_school_year = server.get_school_years()[1]
        with patch.object(server, "DATABASE_PATH", self.database_path):
            server.enroll_student("Earlier learner", "Nursery", school_year, "Red")
            next_year_student = server.enroll_student(
                "New learner", "Nursery", next_school_year, "Blue"
            )
        self.assertEqual(next_year_student["rollNumber"], 1)

    def test_simultaneous_enrollments_receive_distinct_roll_numbers(self):
        school_year = server.get_school_years()[0]
        with patch.object(server, "DATABASE_PATH", self.database_path):
            with ThreadPoolExecutor(max_workers=8) as executor:
                students = list(
                    executor.map(
                        lambda index: server.enroll_student(
                            f"Learner {index}", "Class 1", school_year, "Green"
                        ),
                        range(12),
                    )
                )
        self.assertEqual(
            sorted(student["rollNumber"] for student in students),
            list(range(1, 13)),
        )

    def test_class_capacity_stops_at_roll_number_sixty(self):
        school_year = server.get_school_years()[0]
        with patch.object(server, "DATABASE_PATH", self.database_path):
            for roll_number in range(1, 61):
                enrolled = server.enroll_student(
                    f"Learner {roll_number}", "Class 9", school_year, "Yellow"
                )
            self.assertEqual(enrolled["rollNumber"], 60)
            with self.assertRaises(server.EnrollmentError) as error:
                server.enroll_student(
                    "Extra learner", "Class 9", school_year, "Red"
                )
        self.assertEqual(error.exception.status, 409)

    def test_invalid_class_or_name_is_rejected(self):
        school_year = server.get_school_years()[0]
        with patch.object(server, "DATABASE_PATH", self.database_path):
            with self.assertRaises(server.EnrollmentError):
                server.enroll_student("Learner", "Class 10", school_year, "Red")
            with self.assertRaises(server.EnrollmentError):
                server.enroll_student("   ", "Class 9", school_year, "Red")
            with self.assertRaises(server.EnrollmentError):
                server.enroll_student("Learner", "Class 9", school_year, "Purple")

    def test_roll_roster_includes_numbers_and_names(self):
        school_year = server.get_school_years()[0]
        with patch.object(server, "DATABASE_PATH", self.database_path):
            enrolled = server.enroll_student(
                "Aarav Demo", "Class 8", school_year, "Yellow"
            )
            roster = server.get_class_roster("Class 8", school_year)
        self.assertEqual(
            [
                (student["rollNumber"], student["name"], student["studentId"])
                for student in roster
            ],
            [(1, "Aarav Demo", enrolled["studentId"])],
        )
        self.assertEqual(roster[0]["house"], "Yellow")

    def test_enrollment_is_available_to_student_status_lookup(self):
        school_year = server.get_school_years()[0]
        with patch.object(server, "DATABASE_PATH", self.database_path):
            enrollment = server.enroll_student(
                "Aarav Demo", "Nursery", school_year, "Green"
            )
            server.initialize_database()
            student = server.get_student(enrollment["studentId"])
        self.assertEqual(student["name"], "Aarav Demo")
        self.assertEqual(student["class_name"], "Nursery")
        self.assertEqual(student["status"], "Current student")

    def test_house_assignments_update_and_survive_database_reinitialization(self):
        school_year = server.get_school_years()[0]
        with patch.object(server, "DATABASE_PATH", self.database_path):
            student = server.enroll_student(
                "House learner", "Class 4", school_year, "Red"
            )
            server.assign_student_house(student["studentId"], "Blue")
            server.initialize_database()
            roster = server.get_class_roster("Class 4", school_year)
            search = server.search_students("Find House learner in Blue house")
            name_search = server.search_students("Find House learner")
        self.assertEqual(roster[0]["house"], "Blue")
        self.assertEqual(search["students"][0]["house"], "Blue")
        self.assertEqual(name_search["students"][0]["name"], "House learner")
        self.assertFalse(search["hasMore"])

    def test_student_finder_supports_house_class_id_and_safe_literal_name_search(self):
        school_year = server.get_school_years()[0]
        with patch.object(server, "DATABASE_PATH", self.database_path):
            red_student = server.enroll_student(
                "Ari Percent_100", "Class 4", school_year, "Red"
            )
            server.enroll_student("Bea Blue", "Class 4", school_year, "Blue")
            by_house_class = server.search_students("Show Class 4 in Red house")
            by_id = server.search_students(f"Find {red_student['studentId']}")
            by_name = server.search_students("find Ari Percent_100")
            all_students = server.search_students("show Class 4")
            with self.assertRaises(server.EnrollmentError):
                server.search_students("list students")
        self.assertEqual(by_house_class["students"][0]["studentId"], red_student["studentId"])
        self.assertEqual(by_id["students"][0]["name"], "Ari Percent_100")
        self.assertEqual(by_name["students"][0]["name"], "Ari Percent_100")
        self.assertEqual(len(all_students["students"]), 2)
        self.assertFalse(all_students["hasMore"])

    def test_legacy_enrollments_are_migrated_into_student_lookup(self):
        school_year = server.get_school_years()[0]
        student_id = f"SAGE-{school_year.split('-', 1)[0]}-NUR-003"
        with closing(server.sqlite3.connect(self.database_path)) as connection:
            connection.execute("DROP TABLE student_enrollments")
            connection.execute(
                """
                CREATE TABLE student_enrollments (
                    enrollment_id INTEGER PRIMARY KEY,
                    student_name TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    roll_number INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (academic_year, class_name, roll_number)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO student_enrollments
                    (student_name, class_name, academic_year, roll_number, created_at)
                VALUES (?, 'Nursery', ?, 3, '2025-01-01')
                """,
                ("Legacy learner", school_year),
            )
            connection.commit()
        with patch.object(server, "DATABASE_PATH", self.database_path):
            server.initialize_database()
            student = server.get_student(student_id)
            roster = server.get_class_roster("Nursery", school_year)
        self.assertEqual(student["name"], "Legacy learner")
        self.assertEqual(student["status"], "Current student")
        self.assertEqual(roster[0]["studentId"], student_id)

    def test_fee_changes_and_achievements_survive_database_reinitialization(self):
        with patch.object(server, "DATABASE_PATH", self.database_path):
            updated_fee = server.update_fee_schedule("tuition-early", 27000, True)
            created = server.create_achievement(
                "chess", "Won a school tournament", "Class 6", "FIRST PLACE"
            )
            server.initialize_database()
            fees = server.get_fee_schedule()
            achievements = server.get_achievements()
        self.assertEqual(updated_fee["amount"], 27000)
        self.assertTrue(updated_fee["isConfirmed"])
        self.assertTrue(any(
            fee["feeId"] == "tuition-early" and fee["amount"] == 27000
            for fee in fees
        ))
        self.assertTrue(any(
            achievement["achievementId"] == created["achievementId"]
            for achievement in achievements
        ))

    def test_school_year_choices_start_with_current_academic_year(self):
        self.assertEqual(
            server.get_school_years(datetime(2026, 10, 6)),
            ["2026-27", "2027-28", "2028-29"],
        )


class StaffEnrollmentAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "school.db"
        self.database_patch = patch.object(server, "DATABASE_PATH", self.database_path)
        self.database_patch.start()
        self.environment_patch = patch.dict(
            os.environ,
            {
                "SAGE_ADMIN_USERNAME": "staff",
                "SAGE_ADMIN_PASSWORD": "test-password",
                "SAGE_BUS_VIEWER_CODE": "private-test-code",
                "SAGE_PUBLIC_SCHEME": "http",
            },
        )
        self.environment_patch.start()
        server.staff_sessions.clear()
        server.parent_sessions.clear()
        server.initialize_database()
        self.http_server = server.ThreadingHTTPServer(
            ("127.0.0.1", 0), server.SchoolRequestHandler
        )
        self.http_thread = threading.Thread(
            target=self.http_server.serve_forever, daemon=True
        )
        self.http_thread.start()
        self.origin = f"http://127.0.0.1:{self.http_server.server_port}"
        self.staff_cookie = None
        self.bus_parent_cookie = None

    def tearDown(self):
        self.http_server.shutdown()
        self.http_server.server_close()
        self.http_thread.join()
        server.staff_sessions.clear()
        server.parent_sessions.clear()
        self.environment_patch.stop()
        self.database_patch.stop()
        self.temporary_directory.cleanup()

    def request(
        self, method, path, payload=None, same_origin=True, cookie_header=None
    ):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.http_server.server_port
        )
        headers = {}
        if same_origin:
            headers["Origin"] = self.origin
        cookie_header = self.staff_cookie if cookie_header is None else cookie_header
        if cookie_header:
            headers["Cookie"] = cookie_header
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response_body = json.loads(response.read())
        set_cookie = response.getheader("Set-Cookie")
        if set_cookie and set_cookie.startswith(f"{server.SESSION_COOKIE}="):
            self.staff_cookie = set_cookie.split(";", 1)[0]
        connection.close()
        return response.status, response_body

    def bus_parent_request(self, method, path, payload=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.http_server.server_port
        )
        headers = {"Origin": self.origin}
        if self.bus_parent_cookie:
            headers["Cookie"] = self.bus_parent_cookie
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response_body = json.loads(response.read())
        set_cookie = response.getheader("Set-Cookie")
        if set_cookie and set_cookie.startswith(
            f"{server.BUS_PARENT_SESSION_COOKIE}="
        ):
            self.bus_parent_cookie = set_cookie.split(";", 1)[0]
        connection.close()
        return response.status, response_body

    def sign_in(self):
        return self.request(
            "POST",
            "/api/staff/login",
            {"username": "staff", "password": "test-password"},
        )

    def test_alumni_batch_api_returns_school_provided_counts(self):
        status, alumni = self.request("GET", "/api/alumni-batches")
        self.assertEqual(status, 200)
        self.assertEqual(alumni["batches"][0], {"year": 2019, "graduates": 15})
        self.assertEqual(alumni["batches"][-1], {"year": 2026, "graduates": 60})
        self.assertEqual(alumni["totalGraduates"], 365)

    def test_fee_schedule_and_achievement_lists_are_database_backed(self):
        status, fees = self.request("GET", "/api/fees")
        self.assertEqual(status, 200)
        self.assertFalse(fees["allConfirmed"])
        self.assertEqual(len(fees["fees"]), len(server.DEFAULT_FEES))

        status, achievements = self.request("GET", "/api/achievements")
        self.assertEqual(status, 200)
        self.assertTrue(achievements["allSample"])
        self.assertEqual(len(achievements["achievements"]), len(server.DEFAULT_ACHIEVEMENTS))

    def test_school_notices_and_events_are_staff_published_and_removable(self):
        status, updates = self.request("GET", "/api/school-updates")
        self.assertEqual(status, 200)
        self.assertEqual(updates["updates"], [])

        payload = {
            "type": "notice",
            "title": "Office hours",
            "details": "The school office will be open for family enquiries.",
            "date": None,
        }
        status, _ = self.request("POST", "/api/staff/school-updates", payload)
        self.assertEqual(status, 401)
        self.assertEqual(self.sign_in()[0], 200)

        status, notice = self.request("POST", "/api/staff/school-updates", payload)
        self.assertEqual(status, 201)
        self.assertEqual(notice["type"], "notice")
        self.assertIsNone(notice["date"])

        event_payload = {
            "type": "event",
            "title": "Family meeting",
            "details": "Contact the office to confirm the meeting time.",
            "date": date.today().isoformat(),
        }
        status, event = self.request(
            "POST", "/api/staff/school-updates", event_payload
        )
        self.assertEqual(status, 201)
        status, updates = self.request("GET", "/api/school-updates")
        self.assertEqual(status, 200)
        self.assertEqual(
            [update["updateId"] for update in updates["updates"]],
            [notice["updateId"], event["updateId"]],
        )

        past_event = {**event_payload, "date": "2000-01-01"}
        status, _ = self.request("POST", "/api/staff/school-updates", past_event)
        self.assertEqual(status, 400)
        invalid_update = {**payload, "type": []}
        status, _ = self.request(
            "POST", "/api/staff/school-updates", invalid_update
        )
        self.assertEqual(status, 400)

        status, _ = self.request(
            "DELETE",
            "/api/staff/school-updates",
            {"updateId": notice["updateId"]},
        )
        self.assertEqual(status, 200)
        status, updates = self.request("GET", "/api/school-updates")
        self.assertEqual(status, 200)
        self.assertEqual([update["updateId"] for update in updates["updates"]], [
            event["updateId"],
        ])

    def test_enrollment_returns_id_for_public_status_lookup_and_private_roster(self):
        school_year = server.get_school_years()[0]
        self.assertEqual(self.sign_in()[0], 200)
        status, enrollment = self.request(
            "POST",
            "/api/staff/enroll",
            {
                "name": "Private learner",
                "className": "Nursery",
                "academicYear": school_year,
                "house": "Red",
            },
        )
        self.assertEqual(status, 201)
        expected_year = school_year.split("-", 1)[0]
        self.assertEqual(enrollment["studentId"], f"SAGE-{expected_year}-NUR-001")

        status, student = self.request(
            "GET", f"/api/student?id={enrollment['studentId']}"
        )
        self.assertEqual(status, 200)
        self.assertEqual(student["name"], "Private learner")
        roster_path = (
            f"/api/staff/roster?{urlencode({'className': 'Nursery', 'academicYear': school_year})}"
        )
        status, roster = self.request("GET", roster_path)
        self.assertEqual(status, 200)
        self.assertEqual(roster["students"][0]["studentId"], enrollment["studentId"])
        self.assertEqual(roster["students"][0]["house"], "Red")

    def test_student_finder_is_staff_only_and_returns_house_filtered_matches(self):
        search_url = "/api/staff/student-search?" + urlencode(
            {"q": "Find Kai in Red house"}
        )
        status, _ = self.request("GET", search_url)
        self.assertEqual(status, 401)

        house_update = {
            "studentId": "SAGE-TEST",
            "house": "Blue",
        }
        status, _ = self.request(
            "PUT", "/api/staff/student-house", house_update
        )
        self.assertEqual(status, 401)

        self.assertEqual(self.sign_in()[0], 200)
        school_year = server.get_school_years()[0]
        status, enrollment = self.request(
            "POST",
            "/api/staff/enroll",
            {
                "name": "Kai Sample",
                "className": "Class 4",
                "academicYear": school_year,
                "house": "Red",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(enrollment["house"], "Red")

        search_url = "/api/staff/student-search?" + urlencode(
            {"q": "Find Kai Sample in Class 4 Red house"}
        )
        status, search = self.request("GET", search_url)
        self.assertEqual(status, 200)
        self.assertEqual(len(search["students"]), 1)
        self.assertEqual(search["students"][0]["studentId"], enrollment["studentId"])

        status, updated = self.request(
            "PUT",
            "/api/staff/student-house",
            {"studentId": enrollment["studentId"], "house": "Blue"},
            same_origin=False,
        )
        self.assertEqual(status, 403)
        status, updated = self.request(
            "PUT",
            "/api/staff/student-house",
            {"studentId": enrollment["studentId"], "house": "Blue"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["house"], "Blue")
        status, _ = self.request(
            "PUT",
            "/api/staff/student-house",
            {"studentId": enrollment["studentId"], "house": "Purple"},
        )
        self.assertEqual(status, 400)

        search_url = "/api/staff/student-search?" + urlencode(
            {"q": "Kai Sample"}
        )
        status, search = self.request("GET", search_url)
        self.assertEqual(status, 200)
        self.assertEqual(search["students"][0]["house"], "Blue")
        status, _ = self.request(
            "GET",
            "/api/staff/student-search?" + urlencode({"q": "find student"}),
        )
        self.assertEqual(status, 400)

    def test_enrollment_requires_a_valid_house(self):
        self.assertEqual(self.sign_in()[0], 200)
        status, _ = self.request(
            "POST",
            "/api/staff/enroll",
            {
                "name": "Unassigned Learner",
                "className": "Nursery",
                "academicYear": server.get_school_years()[0],
            },
        )
        self.assertEqual(status, 400)

    def test_fee_mutations_require_staff_and_persist(self):
        payload = {"feeId": "tuition-early", "amount": 27000, "isConfirmed": True}
        status, _ = self.request("PUT", "/api/staff/fees", payload)
        self.assertEqual(status, 401)

        self.assertEqual(self.sign_in()[0], 200)
        status, updated_fee = self.request("PUT", "/api/staff/fees", payload)
        self.assertEqual(status, 200)
        self.assertEqual(updated_fee["amount"], 27000)
        self.assertTrue(updated_fee["isConfirmed"])
        status, fees = self.request("GET", "/api/fees")
        self.assertEqual(status, 200)
        self.assertTrue(fees["allConfirmed"] is False)
        self.assertTrue(any(
            fee["feeId"] == "tuition-early" and fee["amount"] == 27000
            for fee in fees["fees"]
        ))

        invalid_status, _ = self.request(
            "PUT",
            "/api/staff/fees",
            {"feeId": "tuition-early", "amount": 10000001, "isConfirmed": True},
        )
        self.assertEqual(invalid_status, 400)

    def test_achievement_mutations_require_staff_and_reject_sample_deletion(self):
        payload = {
            "sport": "chess",
            "className": "Class 6",
            "title": "Won a school tournament",
            "award": "FIRST PLACE",
        }
        status, _ = self.request("POST", "/api/staff/achievements", payload)
        self.assertEqual(status, 401)
        self.assertEqual(self.sign_in()[0], 200)

        status, created = self.request("POST", "/api/staff/achievements", payload)
        self.assertEqual(status, 201)
        self.assertFalse(created["isSample"])
        status, achievements = self.request("GET", "/api/achievements")
        self.assertEqual(status, 200)
        self.assertIn(created, achievements["achievements"])

        status, _ = self.request(
            "DELETE",
            "/api/staff/achievements",
            {"achievementId": created["achievementId"]},
        )
        self.assertEqual(status, 200)
        status, _ = self.request(
            "DELETE",
            "/api/staff/achievements",
            {"achievementId": achievements["achievements"][-1]["achievementId"]},
        )
        self.assertEqual(status, 404)

    def test_school_logo_is_served_as_svg_image(self):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.http_server.server_port
        )
        connection.request("GET", "/sage-logo.svg")
        response = connection.getresponse()
        logo = response.read().decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "image/svg+xml")
        self.assertIn("Sage High School emblem", logo)
        connection.close()

    def test_student_app_manifest_and_offline_worker_are_served(self):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.http_server.server_port
        )
        connection.request("GET", "/manifest.webmanifest")
        manifest_response = connection.getresponse()
        manifest = json.loads(manifest_response.read())
        self.assertEqual(manifest_response.status, 200)
        self.assertEqual(
            manifest_response.getheader("Content-Type"),
            "application/manifest+json; charset=utf-8",
        )
        self.assertEqual(manifest["display"], "standalone")
        self.assertIn("/sage-logo.svg", [
            icon["src"] for icon in manifest["icons"]
        ])
        for icon_path, expected_size in (
            ("/sage-app-icon-192.png", 192),
            ("/sage-app-icon-512.png", 512),
        ):
            with self.subTest(icon=icon_path):
                connection.request("GET", icon_path)
                icon_response = connection.getresponse()
                icon = icon_response.read()
                self.assertEqual(icon_response.status, 200)
                self.assertEqual(icon_response.getheader("Content-Type"), "image/png")
                self.assertTrue(icon.startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertEqual(struct.unpack(">II", icon[16:24]), (
                    expected_size,
                    expected_size,
                ))

        connection.request("GET", "/service-worker.js")
        worker_response = connection.getresponse()
        worker = worker_response.read().decode("utf-8")
        self.assertEqual(worker_response.status, 200)
        self.assertIn("text/javascript", worker_response.getheader("Content-Type"))
        self.assertIn('requestUrl.pathname.startsWith("/api/")', worker)
        self.assertIn('"/sage-school-life.jpg"', worker)
        self.assertIn('"/sage-app-icon-512.png"', worker)
        self.assertIn('"/creative-studio-photo.jpg"', worker)
        self.assertIn('"/garden-club-photo.jpg"', worker)

        connection.request("GET", "/")
        homepage_response = connection.getresponse()
        homepage = homepage_response.read().decode("utf-8")
        self.assertEqual(homepage_response.status, 200)
        self.assertIn('id="green-club"', homepage)
        self.assertIn('id="admissions"', homepage)
        self.assertIn('href="https://www.sagehighschool.org.in/admissions.html"', homepage)
        self.assertIn("admissions-photo-wall", homepage)
        self.assertIn('src="/creative-studio-photo.jpg"', homepage)
        self.assertIn('src="/garden-club-photo.jpg"', homepage)
        self.assertIn('id="school-updates"', homepage)
        self.assertIn('href="https://unsplash.com/photos/children-painting-ceramic-figures-in-an-art-class-ljfPU1-Ygxw"', homepage)
        self.assertIn('id="install-app"', homepage)
        connection.close()

    def test_vercel_static_build_excludes_database_and_disables_private_features(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = build_static.build_static(temporary_directory)
            homepage = (output_directory / "index.html").read_text(
                encoding="utf-8"
            )
            self.assertIn('src="/static-demo.js"', homepage)
            self.assertIn('href="/static-demo.css"', homepage)
            self.assertIn("PUBLIC WEBSITE PREVIEW", homepage)
            self.assertIn("Official admissions information", homepage)
            self.assertTrue((output_directory / "app.js").is_file())
            self.assertTrue((output_directory / "creative-studio.svg").is_file())
            self.assertTrue((output_directory / "garden-club.svg").is_file())
            self.assertTrue((output_directory / "creative-studio-photo.jpg").is_file())
            self.assertTrue((output_directory / "garden-club-photo.jpg").is_file())
            self.assertFalse((output_directory / "school.db").exists())
            self.assertFalse((output_directory / "server.py").exists())
            self.assertIn("STATIC_DEMO", (output_directory / "app.js").read_text(
                encoding="utf-8"
            ))
            self.assertIn("#staff-portal", (output_directory / "static-demo.css").read_text(
                encoding="utf-8"
            ))

    def test_original_activity_illustrations_are_served_as_lightweight_svg_images(self):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.http_server.server_port
        )
        for image_path, description in (
            ("/creative-studio.svg", "creative studio"),
            ("/garden-club.svg", "garden"),
        ):
            with self.subTest(image=image_path):
                connection.request("GET", image_path)
                response = connection.getresponse()
                image = response.read()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Content-Type"), "image/svg+xml")
                self.assertIn(b"<svg", image)
                self.assertIn(description.encode(), image.lower())
                self.assertLess(len(image), 10_000)
        connection.close()

    def test_carousel_playground_and_sport_photos_are_served_as_jpeg_images(self):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.http_server.server_port
        )
        for photo in (
            "creative-studio-photo.jpg",
            "garden-club-photo.jpg",
            "sage-school-life.jpg",
            "sage-sports-day.jpg",
            "sage-independence-day.jpg",
            "sage-playground.jpg",
            "sport-cricket.jpg",
            "sport-football.jpg",
            "sport-volleyball.jpg",
            "sport-tennis.jpg",
            "sport-badminton.jpg",
            "sport-chess.jpg",
            "sport-carrom.jpg",
            "sport-scrabble.jpg",
            "sport-table-tennis.jpg",
        ):
            with self.subTest(photo=photo):
                connection.request("GET", f"/{photo}")
                response = connection.getresponse()
                image = response.read()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Content-Type"), "image/jpeg")
                self.assertTrue(image.startswith(b"\xff\xd8\xff"))
                self.assertLess(len(image), 100_000)
        connection.close()

    def test_roster_and_enrollment_require_staff_sign_in(self):
        school_year = server.get_school_years()[0]
        status, _ = self.request(
            "GET",
            f"/api/staff/roster?{urlencode({'className': 'Nursery', 'academicYear': school_year})}",
        )
        self.assertEqual(status, 401)

        status, _ = self.request(
            "POST",
            "/api/staff/enroll",
            {
                "name": "Private learner",
                "className": "Nursery",
                "academicYear": school_year,
                "house": "Red",
            },
        )
        self.assertEqual(status, 401)

    def test_cross_site_staff_sign_in_is_rejected(self):
        self.origin = "https://not-the-school.example"
        status, _ = self.sign_in()
        self.assertEqual(status, 403)

    def test_incorrect_staff_password_is_rejected(self):
        status, _ = self.request(
            "POST",
            "/api/staff/login",
            {"username": "staff", "password": "incorrect"},
        )
        self.assertEqual(status, 401)
        self.assertIsNone(self.staff_cookie)

    def test_database_staff_credentials_remain_available_without_environment_values(self):
        with patch.dict(
            os.environ,
            {"SAGE_ADMIN_USERNAME": "", "SAGE_ADMIN_PASSWORD": ""},
        ):
            status, session = self.request("GET", "/api/staff/session")
            self.assertEqual(status, 200)
            self.assertTrue(session["enabled"])
            status, _ = self.sign_in()
            self.assertEqual(status, 200)

    def test_staff_password_is_salted_and_stored_as_a_hash(self):
        with patch.object(server, "DATABASE_PATH", self.database_path):
            with closing(server.connect_database()) as connection:
                row = connection.execute(
                    """
                    SELECT username, password_salt, password_hash
                    FROM staff_users WHERE username = 'staff'
                    """
                ).fetchone()
            self.assertEqual(row["username"], "staff")
            self.assertNotEqual(row["password_hash"], "test-password")
            self.assertEqual(len(row["password_salt"]), 32)
            self.assertTrue(server.authenticate_staff("staff", "test-password"))
            self.assertFalse(server.authenticate_staff("staff", "wrong-password"))

    def test_additional_staff_account_is_created_in_database(self):
        with patch.object(server, "DATABASE_PATH", self.database_path):
            server.create_staff_user("teacher", "a-long-test-password")
            self.assertTrue(
                server.authenticate_staff("teacher", "a-long-test-password")
            )
            with self.assertRaisesRegex(ValueError, "already exists"):
                server.create_staff_user("TEACHER", "another-test-password")
            with self.assertRaisesRegex(ValueError, "at least"):
                server.create_staff_user("shortpass", "short")

    def test_create_staff_command_prompts_and_saves_account(self):
        password = "command-line-test-password"
        with (
            patch.object(server, "DATABASE_PATH", self.database_path),
            patch("builtins.input", return_value="commanduser"),
            patch.object(server.getpass, "getpass", side_effect=[password, password]),
            redirect_stdout(io.StringIO()),
        ):
            server.create_staff_from_prompt()
            self.assertTrue(server.authenticate_staff("commanduser", password))

    def test_staff_can_enroll_and_view_a_private_roster(self):
        school_year = server.get_school_years()[0]
        status, _ = self.sign_in()
        self.assertEqual(status, 200)

        status, enrollment = self.request(
            "POST",
            "/api/staff/enroll",
            {
                "name": "Private learner",
                "className": "Nursery",
                "academicYear": school_year,
                "house": "Green",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(enrollment["rollNumber"], 1)

        status, roster = self.request(
            "GET",
            f"/api/staff/roster?{urlencode({'className': 'Nursery', 'academicYear': school_year})}",
        )
        self.assertEqual(status, 200)
        self.assertEqual(roster["students"][0]["name"], "Private learner")
        public_status, _ = self.request(
            "GET", "/api/student?id=SAGE-PRIVATE-LEARNER"
        )
        self.assertEqual(public_status, 404)

    def test_bus_location_requires_parent_authentication(self):
        status, _ = self.request("GET", "/api/bus/location")
        self.assertEqual(status, 401)

        self.assertEqual(self.sign_in()[0], 200)
        status, _ = self.request("GET", "/api/bus/location")
        self.assertEqual(status, 401)

    def test_parent_and_staff_sessions_are_role_separated(self):
        status, _ = self.bus_parent_request(
            "POST", "/api/bus/parent/login", {"accessCode": "private-test-code"}
        )
        self.assertEqual(status, 200)

        school_year = server.get_school_years()[0]
        roster_path = (
            f"/api/staff/roster?{urlencode({'className': 'Nursery', 'academicYear': school_year})}"
        )
        status, _ = self.request(
            "GET", roster_path, cookie_header=self.bus_parent_cookie
        )
        self.assertEqual(status, 401)
        status, _ = self.bus_parent_request("GET", "/api/bus/location")
        self.assertEqual(status, 200)

    def test_staff_can_share_location_with_signed_in_parent(self):
        self.assertEqual(self.sign_in()[0], 200)
        status, location = self.request(
            "POST",
            "/api/staff/bus-location",
            {"latitude": 17.726, "longitude": 79.152, "accuracy": 12.4},
        )
        self.assertEqual(status, 200)
        self.assertTrue(location["sharing"])
        self.assertTrue(location["active"])

        status, _ = self.bus_parent_request(
            "POST", "/api/bus/parent/login", {"accessCode": "private-test-code"}
        )
        self.assertEqual(status, 200)
        status, shared_location = self.bus_parent_request("GET", "/api/bus/location")
        self.assertEqual(status, 200)
        self.assertEqual(shared_location["latitude"], 17.726)
        self.assertEqual(shared_location["longitude"], 79.152)

    def test_invalid_bus_coordinates_are_rejected(self):
        self.assertEqual(self.sign_in()[0], 200)
        invalid_locations = (
            {"latitude": 91, "longitude": 79, "accuracy": 10},
            {"latitude": 17, "longitude": -181, "accuracy": 10},
            {"latitude": 17, "longitude": 79, "accuracy": -1},
            {"latitude": float("nan"), "longitude": 79, "accuracy": 10},
        )
        for location in invalid_locations:
            with self.subTest(location=location):
                status, _ = self.request(
                    "POST", "/api/staff/bus-location", location
                )
                self.assertEqual(status, 400)

    def test_stop_and_stale_expiry_clear_bus_location(self):
        self.assertEqual(self.sign_in()[0], 200)
        with patch.object(server, "DATABASE_PATH", self.database_path):
            server.save_bus_location(17.726, 79.152, 10)
        status, _ = self.request("POST", "/api/staff/bus-location/stop", {})
        self.assertEqual(status, 200)
        with patch.object(server, "DATABASE_PATH", self.database_path):
            self.assertFalse(server.get_bus_location()["active"])
            server.save_bus_location(17.726, 79.152, 10)
            with closing(server.connect_database()) as connection, connection:
                connection.execute(
                    "UPDATE bus_location SET updated_at = ? WHERE bus_id = 1",
                    (
                        (
                            datetime.now(timezone.utc)
                            - server.BUS_LOCATION_MAX_AGE
                            - timedelta(seconds=1)
                        ).isoformat(),
                    ),
                )
            self.assertFalse(server.get_bus_location()["active"])

    def test_incorrect_parent_code_is_rejected(self):
        status, _ = self.bus_parent_request(
            "POST", "/api/bus/parent/login", {"accessCode": "incorrect"}
        )
        self.assertEqual(status, 401)
        self.assertIsNone(self.bus_parent_cookie)


if __name__ == "__main__":
    unittest.main()
