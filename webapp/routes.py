import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from flask import Response, flash, jsonify, redirect, render_template, request, send_file, stream_with_context, url_for

from .config import ALLOWED_CATEGORIES, DEFAULT_OUTPUT_FORMAT, OUTPUT_FORMATS, ZIP_CATEGORIES
from .services.conversion import (
    media_file_has_audio,
    normalize_output_format,
    run_conversion,
    stream_conversion_events,
    summarize_conversion_log,
)
from .services.files import (
    delete_category_file,
    ensure_directories,
    list_directory,
    resolve_category_file,
    sanitize_filename,
    unique_path,
)


def register_routes(app):
    def handle_upload_request():
        ensure_directories()
        if "files" not in request.files:
            return {
                "success": False,
                "status_code": 400,
                "message": "No files selected for upload.",
                "severity": "warning",
                "results": [],
                "uploaded_count": 0,
                "skipped_count": 0,
            }

        files = request.files.getlist("files")
        results = []
        uploaded_count = 0

        for index, file_storage in enumerate(files):
            if not file_storage or file_storage.filename == "":
                continue

            source_name = file_storage.filename
            safe_name = sanitize_filename(source_name)
            destination = unique_path(ALLOWED_CATEGORIES["uploaded"], safe_name)
            file_storage.save(destination)

            entry = {
                "index": index,
                "source_name": source_name,
                "stored_name": destination.name,
            }
            if not media_file_has_audio(destination):
                destination.unlink(missing_ok=True)
                entry["status"] = "skipped"
                entry["reason"] = "Unsupported media file"
                results.append(entry)
                continue

            uploaded_count += 1
            entry["status"] = "uploaded"
            results.append(entry)

        skipped_count = sum(1 for entry in results if entry["status"] == "skipped")
        if uploaded_count == 0:
            message = "No valid media files were uploaded."
            success = False
            status_code = 400
            severity = "warning"
        elif skipped_count > 0:
            message = f"{uploaded_count} file(s) uploaded. {skipped_count} skipped."
            success = True
            status_code = 200
            severity = "warning"
        else:
            message = f"{uploaded_count} file(s) uploaded and ready to convert."
            success = True
            status_code = 200
            severity = "success"

        return {
            "success": success,
            "status_code": status_code,
            "message": message,
            "severity": severity,
            "results": results,
            "uploaded_count": uploaded_count,
            "skipped_count": skipped_count,
        }

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
        upload_result = handle_upload_request()
        for result in upload_result["results"]:
            if result["status"] == "skipped":
                flash(f"Skipped unsupported media file: {result['source_name']}", "warning")
        flash(upload_result["message"], upload_result["severity"])
        return redirect(url_for("index"))

    @app.route("/upload-async", methods=["POST"])
    def upload_async():
        upload_result = handle_upload_request()
        response_payload = {
            "success": upload_result["success"],
            "message": upload_result["message"],
            "severity": upload_result["severity"],
            "results": upload_result["results"],
            "uploaded_count": upload_result["uploaded_count"],
            "skipped_count": upload_result["skipped_count"],
        }
        return jsonify(response_payload), upload_result["status_code"]

    @app.route("/process", methods=["POST"])
    def process_files():
        output_format = get_selected_output_format()
        ensure_directories()
        if not list_directory("uploaded"):
            flash("Upload at least one file before converting.", "warning")
            return redirect(url_for("index"))

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

    @app.route("/process-stream", methods=["POST"])
    def process_files_stream():
        output_format = get_selected_output_format()
        ensure_directories()
        if not list_directory("uploaded"):
            return jsonify(
                {
                    "success": False,
                    "message": "Upload at least one file before converting.",
                }
            ), 400

        @stream_with_context
        def generate():
            for event in stream_conversion_events(output_format):
                yield f"{json.dumps(event)}\n"

        return Response(generate(), mimetype="application/x-ndjson")

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

    @app.route("/delete/<category>/<filename>", methods=["POST"])
    def delete_file(category: str, filename: str):
        try:
            deleted_file = delete_category_file(category, filename)
        except ValueError:
            flash("Invalid delete request.", "danger")
        except FileNotFoundError:
            flash("File not found.", "warning")
        except OSError as exc:
            flash(f"Could not delete file: {exc}", "danger")
        else:
            flash(f"Deleted {deleted_file.name}.", "success")
        return redirect(url_for("index"))
