import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_DIR = PROJECT_ROOT.parent / "songs"
BASE_DIR = Path(os.environ.get("AUDIO_EXPORTER_STORAGE_DIR", DEFAULT_BASE_DIR)).resolve()
UPLOAD_DIR = BASE_DIR / "uploaded"
CONVERTED_DIR = BASE_DIR / "converted"
# Staging area for uploads being validated; a subfolder so fix_songs.sh (maxdepth 1) never sees it.
INCOMING_DIR = BASE_DIR / ".incoming"
GUARD_BIN_DIR = PROJECT_ROOT / "bin"
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

# Must match KNOWN_EXTENSIONS in fix_songs.sh so upload names map to the same output names.
KNOWN_EXTENSIONS = (
    ".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".opus", ".wma", ".aiff", ".aif", ".alac",
    ".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm", ".wmv", ".flv", ".mpeg", ".mpg",
)

CLEANUP_THRESHOLD_SECONDS = 6 * 60 * 60
CLEANUP_INTERVAL_SECONDS = 60 * 60
# Retention tag thresholds, measured against the file's 6-hour lifetime.
EXPIRY_WARNING_SECONDS = 2 * 60 * 60
EXPIRY_CRITICAL_SECONDS = 60 * 60

DEFAULT_SECRET_KEY = "change-this-secret"
TEMPLATE_FOLDER = PROJECT_ROOT / "templates"
STATIC_FOLDER = PROJECT_ROOT / "static"
