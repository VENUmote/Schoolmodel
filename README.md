# Sage High School demo

A responsive school website with a Python standard-library HTTP server, SQLite-backed enrollments, staff credentials, fee schedule, activity highlights, and cohort results, plus a browser-based student status checker.

## Run locally

Requires Python 3.10 or newer; no third-party packages are required.

```powershell
python server.py
```

Open <http://127.0.0.1:8000>. To use another port, set the `PORT` environment variable before starting the server. Set `SCHOOL_DATABASE` to choose a different SQLite database path.

## Public Vercel demo

The Vercel configuration builds a static, read-only school website. It intentionally omits `school.db`, server code, staff sign-in, student lookup, editable fees, and live bus tracking; those database-backed tools stay available only on the local Python server. The public preview displays the supplied 2019–2026 alumni batch totals and sample school content, and clearly labels the unavailable features. Do not put real student records or staff credentials in the static website.

Build and inspect the safe output locally:

```powershell
python build_static.py
python -m http.server 8001 --directory public
```

After installing Node.js and the Vercel CLI and signing in to the authorised school Vercel account, deploy from the project folder:

```powershell
vercel login
vercel --prod
```

The Vercel build command runs `python build_static.py` and publishes only the generated `public` directory. `.vercelignore` also excludes local SQLite databases and environment files from uploads. Confirm the school has authorised the Vercel project and public domain before publishing.

The homepage follows a classic school layout with a contact strip, school masthead, responsive navigation, and an interactive three-slide carousel featuring photos from the [official Sage High School gallery](https://www.sagehighschool.org.in/gallery.html). A photo-backed admissions section presents the published visit, enquiry, tour, application, and family-meeting steps; confirm current availability and requirements with the Admissions Office. School photos load locally, with the admissions gallery deferred until it is near the viewport. The Creative Studio card uses a locally stored photo of children painting, and the Garden Club card uses a locally stored seedling photo; each links to its [Unsplash source](https://unsplash.com/license). The source images are illustrative references, not photos of Sage students. Nine sport and indoor-game cards use small, linked [Unsplash](https://unsplash.com/license) reference photos; these sport references are not photos of Sage students. The activities list follows the school's [facilities page](https://www.sagehighschool.org.in/facilities.html). A subtle zoom animates activity images. Slide arrows, dots, and the pause control work with mouse, touch, and keyboard; the carousel pauses while focused or hovered. Photo reuse from the school gallery was authorized for this project by the site owner.

The Green Club check-in helps students practise simple campus habits such as reusing paper and sorting waste. Its daily action count is anonymous, saved only in that browser, and never sent to the school server; clear it with the button on the page. It is a personal checklist, not a verified environmental-impact measurement.

The **Notices & upcoming school dates** board is database-backed on the local school server. Signed-in staff can publish school notices and dated events or remove outdated updates; the public page shows notices and upcoming events, not past events. Do not put student names, private contact information, or confidential records in public updates. The static Vercel preview cannot connect to the local update database and directs families to contact the school for current information.

The **Install app** button or your browser's **Install app / Add to Home Screen** menu can add the site to a phone or computer. A service worker caches the app shell and local school photos for a quick return and offline viewing. The staff sign-in, student lookup, fee schedule, achievements, and live bus need a connection; API responses and student records are deliberately not cached. Run over `localhost`/`127.0.0.1` for local development; browsers require HTTPS for installation and service workers on a hosted site.

Use the **color theme** button in the navigation to choose Sage, Ocean, Sunset, or Berry palettes. Your selection is remembered in that browser.

The header, footer, and favicon share the original Sage school-themed SVG emblem in `sage-logo.svg`. It is custom illustrative artwork, not an official school-provided crest; replace it with approved school artwork if available.

## Staff enrollment and roll numbers

Staff accounts, enrollments, the fee schedule, and activity highlights are stored in SQLite. Staff passwords use a unique salt and a PBKDF2-SHA256 hash; passwords are never stored in plaintext. To create a staff account, stop the website server, open PowerShell in the project folder, and run:

```powershell
python server.py --create-staff
```

The command prompts for a username and password without displaying the password as you type. Passwords must be at least 12 characters. Run the command again to create additional accounts; usernames are unique regardless of letter case. It uses the same `school.db` database as the website, or the path configured in `SCHOOL_DATABASE`. Start the site with `python server.py` and sign in using the new credentials. If port 8000 is still in use, set `$env:PORT = "8001"` before starting the site and open <http://127.0.0.1:8001> instead.

For compatibility, setting `SAGE_ADMIN_USERNAME` and `SAGE_ADMIN_PASSWORD` when the database has no staff accounts will create the first account on startup. This only bootstraps an empty staff account table; it does not overwrite existing accounts or passwords. The `--create-staff` prompt is the recommended way to add credentials.

Use the same credentials in the Staff portal on the website. Only authenticated staff can add a student, view class lists, assign a student to the Red, Blue, Yellow, or Green house, edit the example fee schedule, and add or remove activity highlights. The roster lets staff assign or change existing students' houses; migrated records start unassigned until staff chooses a house. The server assigns roll numbers sequentially from 1 to 60 separately for each Nursery, LKG, UKG, or Class 1–9 roster and academic year. New enrollments receive a student ID based on their school year, class, and roll number; the public status checker can look up that ID. A new academic year's rolls start again at 1; a class that already has 60 students cannot accept another enrollment.

The **Student finder chat** is a staff-only, local search assistant for enrolled students. Try a name or student ID, or ask for a class or house (for example, “Class 4 in Red house”). It searches the school database on this server, returns at most 20 matches at a time, and does not send student records to an external AI service. It is a chat-style search helper, not a generative AI service.

Fee edits and activity highlights update SQLite and appear on the public page. Fee amounts start as examples and are clearly marked unconfirmed until staff explicitly mark each item approved. Activity highlights are stored without student names or photos; staff should enter only school-approved, non-identifying information. To back up the local database, stop the server and copy `school.db` to a protected location; also protect any alternate file selected with `SCHOOL_DATABASE`.

The public status checker reveals a student's name and class to anyone who knows the ID. This local demo server binds to `127.0.0.1` and is not ready to host real student records on the public internet. Use fictional records only; do not expose it publicly or use it over an untrusted network. A real deployment needs authenticated and authorised student lookups, HTTPS, production-grade credential and session management, protected database backups, and school-approved privacy and retention policies.

## School map and live bus

The school map currently searches Google Maps for “Sage High School, Jangaon, Telangana.” It is a search result, not a verified campus pin; confirm the exact address with the school before using it for directions.

Live Bus 01 tracking is disabled until a school configures a private parent-viewer code. To try it locally in PowerShell, set the code and the staff login before starting the server:

```powershell
$secureBusCode = Read-Host "Enter a strong private parent bus access code" -AsSecureString
$env:SAGE_BUS_VIEWER_CODE = [System.Net.NetworkCredential]::new("", $secureBusCode).Password
python server.py
```

Keep the parent code private and share it only with authorised families. Anyone who has this shared demo code can view the current Bus 01 location while it is being shared; use a production-grade, individually authorised parent system before real deployment. The driver signs in through the staff portal on the bus phone, taps **Start GPS sharing**, grants location permission, and taps **Stop trip & clear location** when finished. Parents sign in in the Live bus section and can open the current coordinates in Google Maps. Location updates are stored in SQLite, visible only to an authenticated parent session, expire after 90 seconds without a fresh update, and are cleared when staff stops sharing or signs out.

Browser GPS requires HTTPS on a reachable website (localhost is allowed for local development). The demo server binds to `127.0.0.1`, so a phone cannot reach it over the network; cross-device use requires a properly secured deployment behind HTTPS. If TLS is terminated by a trusted reverse proxy, set `$env:SAGE_PUBLIC_SCHEME = "https"` before starting the server so same-origin checks and secure session cookies match the public HTTPS address. Do not expose this demo server or publish real bus locations or student data without school approval and a production security review.

## Demo data and privacy

The student IDs, tuition and sample bus fares are fictional examples for Sage High School in Jangaon, Telangana. The graduating-batch student counts from 2019 through 2026 are supplied by the school owner. The first Class 10 batch passed out in 2019. The site totals eight graduating batches at 365 students. The bus fare estimator demonstrates optional annual fees for three example distance bands; these do not describe actual routes, availability, or approved school prices. Confirm current transport fees and stops with the school office.

The activities page includes sample sports and a filterable achievement wall. The initial highlights are fictional examples, not verified student results; staff can add non-identifying, school-approved highlights and remove entries they have added. Do not publish identifiable student information without approval from the school, student, and guardian.

The academic section offers early-years and Classes 1–8 NCERT/NCF-aligned learning outlines, and topic summaries with links to the CBSE secondary subject syllabus published for 2025–26. Always check CBSE's curriculum portal for the latest academic year and confirm the school's adopted textbooks and subject combinations.

The status checker is a public ID lookup, so this demo must not be populated with real student records as-is. Before using real school data, add appropriate authentication, authorisation, consent, retention, and privacy protections. Confirm the school contact information, activities, and fee schedule before publishing.

The alumni chart and total are computed from the school-provided graduating-batch counts in SQLite. Those year counts are updated from the configured school data when the server starts.

## Tests

```powershell
python -m unittest
```
