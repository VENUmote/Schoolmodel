from pathlib import Path
from shutil import copy2


ROOT = Path(__file__).resolve().parent
PUBLIC_FILES = (
    "app.js",
    "creative-studio.svg",
    "creative-studio-photo.jpg",
    "garden-club.svg",
    "garden-club-photo.jpg",
    "manifest.webmanifest",
    "sage-app-icon-192.png",
    "sage-app-icon-512.png",
    "sage-independence-day.jpg",
    "sage-logo.svg",
    "sage-playground.jpg",
    "sage-school-life.jpg",
    "sage-sports-day.jpg",
    "service-worker.js",
    "static-demo.css",
    "static-demo.js",
    "sport-badminton.jpg",
    "sport-carrom.jpg",
    "sport-chess.jpg",
    "sport-cricket.jpg",
    "sport-football.jpg",
    "sport-scrabble.jpg",
    "sport-table-tennis.jpg",
    "sport-tennis.jpg",
    "sport-volleyball.jpg",
    "styles.css",
)
APP_SCRIPT = '<script src="/app.js" defer></script>'
STATIC_BANNER = """<aside class="static-demo-notice" role="status">
      <span>PUBLIC WEBSITE PREVIEW</span>
      <p>Student records, staff sign-in, fees, and live bus tracking are not available on this static demo. Live school notices and event dates are published by authorised staff on the school website.</p>
      <a href="https://www.sagehighschool.org.in/admissions.html" target="_blank" rel="noopener noreferrer">Official admissions information <span aria-hidden="true">↗</span></a>
    </aside>"""


def build_static(output_directory=None):
    output_directory = Path(output_directory or ROOT / "public").resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    unexpected_files = sorted(
        entry.name
        for entry in output_directory.iterdir()
        if entry.name not in {*PUBLIC_FILES, "index.html"}
    )
    if unexpected_files:
        raise ValueError(
            "Refusing to include unexpected files in the Vercel output directory: "
            + ", ".join(unexpected_files)
        )

    for filename in PUBLIC_FILES:
        source = ROOT / filename
        if not source.is_file():
            raise FileNotFoundError(f"Required public asset is missing: {source}")

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    if html.count(APP_SCRIPT) != 1:
        raise ValueError("Could not find the unique application script in index.html.")
    html = html.replace(
        '<link rel="stylesheet" href="/styles.css">',
        '<link rel="stylesheet" href="/styles.css">\n'
        '    <link rel="stylesheet" href="/static-demo.css">',
        1,
    )
    html = html.replace(
        APP_SCRIPT,
        '<script src="/static-demo.js" defer></script>\n    ' + APP_SCRIPT,
        1,
    )
    if html.count('<main id="main">') != 1:
        raise ValueError("Could not find the unique main element in index.html.")
    html = html.replace(
        '<main id="main">',
        '<main id="main">\n    ' + STATIC_BANNER,
        1,
    )

    for filename in PUBLIC_FILES:
        copy2(ROOT / filename, output_directory / filename)
    (output_directory / "index.html").write_text(html, encoding="utf-8")
    return output_directory


if __name__ == "__main__":
    print(f"Created safe, static-only Vercel output at {build_static()}")
