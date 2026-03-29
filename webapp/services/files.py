import time
from datetime import datetime
from pathlib import Path

from ..config import ALLOWED_CATEGORIES, BASE_DIR, CLEANUP_THRESHOLD_SECONDS, CONVERTED_DIR, UPLOAD_DIR


def ensure_directories():
    for directory in (UPLOAD_DIR, CONVERTED_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    safe = "".join(ch for ch in name if ch.isalnum() or ch in (" ", ".", "-", "_"))
    safe = safe.strip().lstrip(".")
    if not safe:
        return "file"
    return safe


def unique_path(directory: Path, filename: str) -> Path:
    base_name = sanitize_filename(filename)
    candidate = directory / base_name
    stem = candidate.stem
    suffix = candidate.suffix
    count = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{count}{suffix}"
        count += 1
    return candidate


def list_directory(category: str):
    directory = ALLOWED_CATEGORIES[category]
    files = []
    if directory.exists():
        for path in directory.iterdir():
            if path.is_file():
                files.append(
                    {
                        "name": path.name,
                        "size": path.stat().st_size,
                        "modified": datetime.fromtimestamp(path.stat().st_mtime),
                    }
                )
    files.sort(key=lambda entry: entry["modified"], reverse=True)
    return files


def cleanup_media_files():
    now = time.time()
    removed = []
    for directory in (UPLOAD_DIR, CONVERTED_DIR):
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
                print(f"Failed to remove file {path}: {exc}")
    if removed:
        removed_names = ", ".join(str(path.name) for path in removed)
        print(f"Cleaned up media files: {removed_names}")
    return removed


def validate_category(category: str):
    if category not in ALLOWED_CATEGORIES:
        raise ValueError("Invalid category")


def resolve_category_file(category: str, filename: str) -> Path:
    validate_category(category)
    safe_name = Path(filename).name
    if safe_name != filename:
        raise ValueError("Invalid filename")
    file_path = ALLOWED_CATEGORIES[category] / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError("File not found")
    file_path = file_path.resolve()
    if not str(file_path).startswith(str(BASE_DIR.resolve())):
        raise ValueError("Invalid filename")
    return file_path


def delete_category_file(category: str, filename: str) -> Path:
    file_path = resolve_category_file(category, filename)
    file_path.unlink()
    return file_path
