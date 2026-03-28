from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from flask import flash, redirect, render_template, request, send_file, url_for

from .config import ALLOWED_CATEGORIES, DEFAULT_OUTPUT_FORMAT, OUTPUT_FORMATS, ZIP_CATEGORIES
from .services.conversion import (
    media_file_has_audio,
    normalize_output_format,
    run_conversion,
    summarize_conversion_log,
)
from .services.files import ensure_directories, list_directory, resolve_category_file, sanitize_filename, unique_path


def register_routes(app):
    def render_index_page():
        ensure_directories()
        return render_template(
            "index.html",
            uploaded_files=list_directory("uploaded"),
            converted_files=list_directory("converted"),
            output_formats=OUTPUT_FORMATS,
            default_output_format=DEFAULT_OUTPUT_FORMAT,
        )

    def get_selected_output_format() -> str:
        requested_format = request.form.get("output_format")
        normalized_format = normalize_output_format(requested_format)
        if requested_format and requested_format.lower() != normalized_format:
            flash(
                f"Unsupported output format '{requested_format}'. Using {normalized_format.upper()} instead.",
                "warning",
            )
        return normalized_format

    @app.route("/", methods=["GET"])
    def index():
        return render_index_page()

    @app.route("/upload", methods=["POST"])
    def upload():
        ensure_directories()
        output_format = get_selected_output_format()
        if "files" not in request.files:
            flash("No files selected for upload.", "warning")
            return redirect(url_for("index"))

        files = request.files.getlist("files")
        uploaded_count = 0
        for file_storage in files:
            if not file_storage or file_storage.filename == "":
                continue
            safe_name = sanitize_filename(file_storage.filename)
            destination = unique_path(ALLOWED_CATEGORIES["uploaded"], safe_name)
            file_storage.save(destination)
            if not media_file_has_audio(destination):
                destination.unlink(missing_ok=True)
                flash(f"Skipped unsupported media file: {file_storage.filename}", "warning")
                continue
            uploaded_count += 1

        if uploaded_count == 0:
            flash("No valid media files were uploaded.", "warning")
            return redirect(url_for("index"))

        success, output = run_conversion(output_format)
        converted, skipped, failed = summarize_conversion_log(output)
        if output:
            flash(output, "info")
        if success:
            flash(
                f"{uploaded_count} file(s) uploaded. Conversion to {output_format.upper()} finished. "
                f"{converted} converted, {skipped} skipped, {failed} failed.",
                "success",
            )
        else:
            flash(
                f"{uploaded_count} file(s) uploaded. Conversion to {output_format.upper()} finished with errors. "
                f"{converted} converted, {skipped} skipped, {failed} failed.",
                "danger",
            )
        return redirect(url_for("index"))

    @app.route("/process", methods=["POST"])
    def process_files():
        output_format = get_selected_output_format()
        ensure_directories()
        success, output = run_conversion(output_format)
        converted, skipped, failed = summarize_conversion_log(output)
        if output:
            flash(output, "info")
        if success:
            flash(
                f"Processing to {output_format.upper()} finished. {converted} converted, {skipped} skipped, {failed} failed.",
                "success",
            )
        else:
            flash(
                f"Processing to {output_format.upper()} finished with errors. {converted} converted, {skipped} skipped, {failed} failed.",
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
            flash("ZIP download is only available for processed files.", "danger")
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
