import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_DIR = PROJECT_ROOT.parent / "songs"
BASE_DIR = Path(os.environ.get("AUDIO_EXPORTER_STORAGE_DIR", DEFAULT_BASE_DIR)).resolve()
UPLOAD_DIR = BASE_DIR / "uploaded"
CONVERTED_DIR = BASE_DIR / "converted"
SCRIPT_PATH = Path(os.environ.get("AUDIO_EXPORTER_SCRIPT_PATH", PROJECT_ROOT / "fix_songs.sh")).resolve()

ALLOWED_CATEGORIES = {
    "uploaded": UPLOAD_DIR,
    "converted": CONVERTED_DIR,
}
ZIP_CATEGORIES = {"converted"}
OUTPUT_FORMATS = {
    "mp3": {"label": "MP3", "extension": ".mp3"},
    "flac": {"label": "FLAC", "extension": ".flac"},
}
DEFAULT_OUTPUT_FORMAT = "mp3"

CLEANUP_THRESHOLD_SECONDS = 6 * 60 * 60
CLEANUP_INTERVAL_SECONDS = 60 * 60

DEFAULT_SECRET_KEY = "change-this-secret"
TEMPLATE_FOLDER = PROJECT_ROOT / "templates"
STATIC_FOLDER = PROJECT_ROOT / "static"
