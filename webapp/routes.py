from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from flask import flash, redirect, render_template, request, send_file, url_for

from .config import ALLOWED_CATEGORIES, ZIP_CATEGORIES
from .services.conversion import run_conversion, summarize_conversion_log
from .services.files import (
    ensure_directories,
    list_directory,
    resolve_category_file,
    sanitize_filename,
    unique_path,
)


def register_routes(app):
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
            destination = unique_path(ALLOWED_CATEGORIES["uploaded"], safe_name)
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
            flash(
                f"{uploaded_count} file(s) uploaded. Conversion finished. "
                f"{converted} converted, {skipped} skipped, {failed} failed.",
                "success",
            )
        else:
            flash(
                f"{uploaded_count} file(s) uploaded. Conversion finished with errors. "
                f"{converted} converted, {skipped} skipped, {failed} failed.",
                "danger",
            )
        return redirect(url_for("index"))

    @app.route("/process", methods=["POST"])
    def process_files():
        ensure_directories()
        success, output = run_conversion()
        converted, skipped, failed = summarize_conversion_log(output)
        if output:
            flash(output, "info")
        if success:
            flash(
                f"Processing finished. {converted} converted, {skipped} skipped, {failed} failed.",
                "success",
            )
        else:
            flash(
                f"Processing finished with errors. {converted} converted, {skipped} skipped, {failed} failed.",
                "danger",
            )
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
                path = ALLOWED_CATEGORIES[category] / Path(item["name"]).name
                archive.write(path, arcname=path.name)
        memory_file.seek(0)
        return send_file(
            memory_file,
            as_attachment=True,
            download_name=f"{category}.zip",
            mimetype="application/zip",
        )
