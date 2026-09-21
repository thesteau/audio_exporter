import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from ..config import (
    ALLOWED_CATEGORIES,
    BASE_DIR,
    CLEANUP_THRESHOLD_SECONDS,
    CONVERTED_DIR,
    INCOMING_DIR,
    KNOWN_EXTENSIONS,
    UPLOAD_DIR,
)

_upload_name_lock = threading.Lock()


def safe_console_text(value: str) -> str:
    return value.encode("ascii", errors="backslashreplace").decode("ascii")


def ensure_directories():
    for directory in (UPLOAD_DIR, CONVERTED_DIR, INCOMING_DIR):
        directory.mkdir(parents=True, exist_ok=True)


SAFE_FILENAME_CHARACTERS = frozenset(" .-_()[]&',!+#@~=")


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    safe = "".join(ch for ch in name if ch.isalnum() or ch in SAFE_FILENAME_CHARACTERS)
    safe = safe.strip().lstrip(".")
    if not safe:
        return "file"
    return safe


def conversion_stem(filename: str) -> str:
    """Mirror strip_known_extensions in fix_songs.sh: the base name the converted file will use."""
    stem = filename
    while True:
        lowered = stem.lower()
        extension = next((ext for ext in KNOWN_EXTENSIONS if lowered.endswith(ext)), None)
        if extension is None:
            return stem
        stem = stem[: -len(extension)]


def converted_name_for(filename: str, output_format: str) -> str:
    """Mirror build_converted_name in fix_songs.sh."""
    return f"{conversion_stem(filename) or 'converted'}.{output_format}"


def pending_conversions(output_format: str) -> list[str]:
    """Uploaded files that have no output in this format yet (what the script will actually convert)."""
    return sorted(
        entry["name"]
        for entry in list_directory("uploaded")
        if not (CONVERTED_DIR / converted_name_for(entry["name"], output_format)).exists()
    )


def purge_stale_temp_files():
    """At startup nothing is in flight, so leftover staged uploads and partial outputs are junk."""
    stale = [path for path in INCOMING_DIR.iterdir() if path.is_file()]
    stale += [path for path in CONVERTED_DIR.glob(".partial-*") if path.is_file()]
    for path in stale:
        try:
            path.unlink()
        except OSError as exc:
            print(safe_console_text(f"Failed to remove stale temp file {path}: {exc}"))


def unique_upload_path(filename: str) -> Path:
    """Pick an upload name whose converted output name is not already claimed.

    Checks existing uploads and existing outputs, so the script never skips a new upload as
    "already converted" because of a stale output, and two uploads never target one output.
    """
    base_name = sanitize_filename(filename)
    base = Path(base_name)
    taken = {
        conversion_stem(path.name).lower()
        for directory in (UPLOAD_DIR, CONVERTED_DIR)
        for path in directory.iterdir()
        if path.is_file() and not path.name.startswith(".")
    }
    candidate = base_name
    count = 2
    while conversion_stem(candidate).lower() in taken:
        candidate = f"{base.stem}-{count}{base.suffix}"
        count += 1
    return UPLOAD_DIR / candidate


def stage_upload(file_storage) -> Path:
    """Save an upload outside the uploaded folder so conversions never see a half-written file."""
    staged = INCOMING_DIR / uuid.uuid4().hex
    file_storage.save(staged)
    return staged


def commit_upload(staged: Path, source_name: str) -> Path:
    with _upload_name_lock:
        destination = unique_upload_path(source_name)
        os.replace(staged, destination)
    return destination


def list_directory(category: str):
    directory = ALLOWED_CATEGORIES[category]
    files = []
    if directory.exists():
        for path in directory.iterdir():
            if path.name.startswith("."):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if path.is_file():
                files.append(
                    {
                        "name": path.name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime),
                        "modified_ts": stat.st_mtime,
                    }
                )
    files.sort(key=lambda entry: entry["modified"], reverse=True)
    return files


def cleanup_media_files():
    now = time.time()
    removed = []
    for directory in (UPLOAD_DIR, CONVERTED_DIR, INCOMING_DIR):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if not path.is_file():
                continue
            try:
                file_age = now - path.stat().st_mtime
                if file_age > CLEANUP_THRESHOLD_SECONDS:
                    path.unlink()
                    removed.append(path)
            except OSError as exc:
                print(safe_console_text(f"Failed to remove file {path}: {exc}"))
    if removed:
        removed_names = ", ".join(str(path.name) for path in removed)
        print(safe_console_text(f"Cleaned up media files: {removed_names}"))
    return removed


def validate_category(category: str):
    if category not in ALLOWED_CATEGORIES:
        raise ValueError("Invalid category")


def resolve_category_file(category: str, filename: str) -> Path:
    validate_category(category)
    safe_name = Path(filename).name
    if safe_name != filename or safe_name.startswith("."):
        raise ValueError("Invalid filename")
    file_path = ALLOWED_CATEGORIES[category] / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError("File not found")
    file_path = file_path.resolve()
    if not file_path.is_relative_to(BASE_DIR.resolve()):
        raise ValueError("Invalid filename")
    return file_path


def delete_category_file(category: str, filename: str) -> Path:
    file_path = resolve_category_file(category, filename)
    file_path.unlink()
    return file_path
