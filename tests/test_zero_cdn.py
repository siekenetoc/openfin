from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = [
    "cdn.jsdelivr",
    "jsdelivr.net",
    "unpkg.com",
    "cdnjs.cloudflare.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "cdn.tailwindcss.com",
    "code.jquery.com",
]


def test_no_external_cdn_references():
    offenders = []
    for path in list((PROJECT_ROOT / "templates").rglob("*.html")) + list(
        (PROJECT_ROOT / "static" / "src").rglob("*")
    ):
        if not path.is_file():
            continue
        text = path.read_text(errors="ignore").lower()
        for needle in FORBIDDEN:
            if needle in text:
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {needle}")
    assert offenders == [], offenders


def test_assets_are_local():
    base = (PROJECT_ROOT / "templates" / "base.html").read_text()
    assert "dist/css/app.min.css" in base
    assert "dist/js/app.min.js" in base
    assert "http://" not in base
    assert "https://" not in base
