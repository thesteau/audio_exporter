import os
import subprocess
import threading
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from flask import Flask, flash, redirect, render_template, request, send_file, url_for

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
_cleanup_thread_started = False

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret")


def ensure_directories():
    for directory in (UPLOAD_DIR, OLD_DIR, CONVERTED_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    safe = "".join(ch for ch in name if ch.isalnum() or ch in (" ", ".", "-", "_"))
    safe = safe.strip()
    if not safe:
        return "file.mp3"
    if safe.startswith("."):
        safe = safe.lstrip(".")
    if not safe.lower().endswith(".mp3"):
        safe += ".mp3"
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
                files.append({
                    "name": path.name,
                    "size": path.stat().st_size,
                    "modified": datetime.fromtimestamp(path.stat().st_mtime),
                })
    files.sort(key=lambda entry: entry["modified"], reverse=True)
    return files


def cleanup_old_music_files():
    now = time.time()
    removed = []
    for directory in (UPLOAD_DIR, OLD_DIR, CONVERTED_DIR):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if not path.is_file() or path.suffix.lower() != ".mp3":
                continue
            try:
                file_age = now - path.stat().st_mtime
                if file_age > CLEANUP_THRESHOLD_SECONDS:
                    path.unlink()
                    removed.append(path)
            except OSError as exc:
                print(f"Failed to remove old file {path}: {exc}")
    if removed:
        removed_names = ", ".join(str(path.name) for path in removed)
        print(f"Cleaned up old MP3 files: {removed_names}")
    return removed


def cleanup_worker():
    while True:
        time.sleep(CLEANUP_INTERVAL_SECONDS)
        cleanup_old_music_files()


def ensure_cleanup_thread():
    global _cleanup_thread_started
    if not _cleanup_thread_started:
        _cleanup_thread_started = True
        thread = threading.Thread(target=cleanup_worker, daemon=True)
        thread.start()


def run_conversion():
    if not SCRIPT_PATH.exists():
        return False, "Conversion script not found."
    try:
        result = subprocess.run(
            [str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            check=False,
            cwd="/app",
        )
    except Exception as exc:
        return False, f"Conversion execution failure: {exc}"

    output = result.stdout.strip()
    if result.stderr.strip():
        output = f"{output}\n{result.stderr.strip()}" if output else result.stderr.strip()
    return result.returncode == 0, output


def summarize_conversion_log(log_text: str):
    converted = skipped = failed = 0
    for line in log_text.splitlines():
        if line.startswith("Converted successfully:"):
            converted += 1
        elif line.startswith("Skipping already converted:"):
            skipped += 1
        elif line.startswith("Failed conversion:"):
            failed += 1
    return converted, skipped, failed


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


@app.before_first_request
def startup():
    ensure_directories()
    cleanup_old_music_files()
    ensure_cleanup_thread()


@app.route("/", methods=["GET"])
def index():
    ensure_directories()
    return render_template(
        "index.html",
        uploaded_files=list_directory("uploaded"),
        old_files=list_directory("old"),
        converted_files=list_directory("converted"),
    )


@app.route("/upload", methods=["POST"])
def upload():
    ensure_directories()
    if "files" not in request.files:
        flash("No files selected for upload.", "warning")
        return redirect(url_for("index"))

    files = request.files.getlist("files")
    uploaded_count = 0
    for file_storage in files:
        if not file_storage or file_storage.filename == "":
            continue
        safe_name = sanitize_filename(file_storage.filename)
        if not safe_name.lower().endswith(".mp3"):
            flash(f"Skipped invalid file: {file_storage.filename}", "warning")
            continue
        destination = unique_path(UPLOAD_DIR, safe_name)
        file_storage.save(destination)
        uploaded_count += 1

    if uploaded_count == 0:
        flash("No valid MP3 files were uploaded.", "warning")
        return redirect(url_for("index"))

    success, output = run_conversion()
    converted, skipped, failed = summarize_conversion_log(output)
    if output:
        flash(output, "info")
    if success:
        flash(f"{uploaded_count} file(s) uploaded. Conversion finished. {converted} converted, {skipped} skipped, {failed} failed.", "success")
    else:
        flash(f"{uploaded_count} file(s) uploaded. Conversion finished with errors. {converted} converted, {skipped} skipped, {failed} failed.", "danger")
    return redirect(url_for("index"))


@app.route("/process", methods=["POST"])
def process_files():
    ensure_directories()
    success, output = run_conversion()
    converted, skipped, failed = summarize_conversion_log(output)
    if output:
        flash(output, "info")
    if success:
        flash(f"Processing finished. {converted} converted, {skipped} skipped, {failed} failed.", "success")
    else:
        flash(f"Processing finished with errors. {converted} converted, {skipped} skipped, {failed} failed.", "danger")
    return redirect(url_for("index"))


@app.route("/download/<category>/<filename>", methods=["GET"])
def download_file(category: str, filename: str):
    try:
        file_path = resolve_category_file(category, filename)
    except ValueError:
        flash("Invalid download request.", "danger")
        return redirect(url_for("index"))
    except FileNotFoundError:
        flash("File not found.", "warning")
        return redirect(url_for("index"))

    return send_file(str(file_path), as_attachment=True, download_name=file_path.name)


@app.route("/download-zip/<category>", methods=["GET"])
def download_zip(category: str):
    if category not in ZIP_CATEGORIES:
        flash("ZIP download is only available for old and converted files.", "danger")
        return redirect(url_for("index"))

    files = list_directory(category)
    if not files:
        flash(f"No files available in {category} to zip.", "warning")
        return redirect(url_for("index"))

    memory_file = BytesIO()
    with ZipFile(memory_file, "w", ZIP_DEFLATED) as archive:
        for item in files:
            path = ALLOWED_CATEGORIES[category] / item["name"]
            archive.write(path, arcname=item["name"])
    memory_file.seek(0)
    return send_file(
        memory_file,
        as_attachment=True,
        download_name=f"{category}.zip",
        mimetype="application/zip",
    )


if __name__ == "__main__":
    ensure_directories()
    app.run(host="0.0.0.0", port=8000)
