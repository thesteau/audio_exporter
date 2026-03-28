from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = Path("/service/songs")
UPLOAD_DIR = BASE_DIR / "uploaded"
OLD_DIR = BASE_DIR / "old"
CONVERTED_DIR = BASE_DIR / "converted"
SCRIPT_PATH = Path("/app/fix_songs.sh")

ALLOWED_CATEGORIES = {
    "uploaded": UPLOAD_DIR,
    "old": OLD_DIR,
    "converted": CONVERTED_DIR,
}
ZIP_CATEGORIES = {"old", "converted"}

CLEANUP_THRESHOLD_SECONDS = 6 * 60 * 60
CLEANUP_INTERVAL_SECONDS = 6 * 60 * 60

DEFAULT_SECRET_KEY = "change-this-secret"
TEMPLATE_FOLDER = PROJECT_ROOT / "templates"
STATIC_FOLDER = PROJECT_ROOT / "static"
