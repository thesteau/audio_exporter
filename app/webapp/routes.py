import json
import shutil
import time
from pathlib import Path

from flask import Response, flash, jsonify, redirect, render_template, request, send_file, stream_with_context, url_for

from .config import (
    ALLOWED_CATEGORIES,
    BASE_DIR,
    CLEANUP_INTERVAL_SECONDS,
    CLEANUP_THRESHOLD_SECONDS,
    DEFAULT_OUTPUT_FORMAT,
    EXPIRY_CRITICAL_SECONDS,
    EXPIRY_WARNING_SECONDS,
    MAX_UPLOAD_BYTES,
    MIN_FREE_BYTES,
    OUTPUT_FORMATS,
    ZIP_CATEGORIES,
)
from .runtime import estimate_deletion_time
from .services.conversion import (
    BUSY_MESSAGE,
    conversion_in_progress,
    media_file_has_audio,
    normalize_output_format,
    run_conversion,
    stream_conversion_events,
    summarize_conversion_log,
)
from .services.files import (
    commit_upload,
    delete_category_file,
    ensure_directories,
    list_directory,
    pending_conversions,
    resolve_category_file,
    stage_upload,
    stream_zip,
)


def retention_state(expires_at: float, now: float) -> str:
    remaining = expires_at - now
    if remaining <= EXPIRY_CRITICAL_SECONDS:
        return "deleting"
    if remaining <= EXPIRY_WARNING_SECONDS:
        return "expiring"
    return "active"


def list_with_retention(category: str, now: float):
    files = list_directory(category)
    for entry in files:
        entry["expires_at"] = entry["modified_ts"] + CLEANUP_THRESHOLD_SECONDS
        entry["delete_at"] = estimate_deletion_time(entry["modified_ts"])
        entry["retention"] = retention_state(entry["expires_at"], now)
    return files


def format_bytes(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" or size >= 10 else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def format_remaining(seconds: float) -> str:
    minutes = max(0, int(seconds // 60))
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m" if minutes else "<1m"


def register_routes(app):
    app.jinja_env.filters["filesize"] = format_bytes
    app.jinja_env.filters["remaining"] = format_remaining

    def upload_rejection(status_code: int, message: str):
        return {
            "success": False,
            "status_code": status_code,
            "message": message,
            "severity": "danger",
            "results": [],
            "uploaded_count": 0,
            "skipped_count": 0,
        }

    def handle_upload_request():
        ensure_directories()
        # Check before touching request.files, which would read the whole body to disk.
        incoming_bytes = request.content_length or 0
        if incoming_bytes > MAX_UPLOAD_BYTES:
            return upload_rejection(413, f"File too large. Limit is {format_bytes(MAX_UPLOAD_BYTES)}.")
        free_bytes = shutil.disk_usage(BASE_DIR).free
        if free_bytes - incoming_bytes < MIN_FREE_BYTES:
            return upload_rejection(507, f"Not enough disk space on the server ({format_bytes(free_bytes)} free).")
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
            entry = {"index": index, "source_name": source_name}
            try:
                staged = stage_upload(file_storage)
            except OSError as exc:
                entry["status"] = "skipped"
                entry["reason"] = f"Could not save: {exc.strerror or exc}"
                results.append(entry)
                continue
            if not media_file_has_audio(staged):
                staged.unlink(missing_ok=True)
                entry["status"] = "skipped"
                entry["reason"] = "No audio track found"
                results.append(entry)
                continue

            destination = commit_upload(staged, source_name)
            uploaded_count += 1
            entry["stored_name"] = destination.name
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
        now = time.time()
        return render_template(
            "index.html",
            uploaded_files=list_with_retention("uploaded", now),
            converted_files=list_with_retention("converted", now),
            output_formats=OUTPUT_FORMATS,
            default_output_format=DEFAULT_OUTPUT_FORMAT,
            server_now=now,
            retention_hours=CLEANUP_THRESHOLD_SECONDS // 3600,
            sweep_minutes=CLEANUP_INTERVAL_SECONDS // 60,
            expiry_warning=EXPIRY_WARNING_SECONDS,
            expiry_critical=EXPIRY_CRITICAL_SECONDS,
            conversion_running=conversion_in_progress(),
            max_upload_bytes=MAX_UPLOAD_BYTES,
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

        if not pending_conversions(output_format):
            flash(f"Everything is already converted to {output_format.upper()}.", "info")
            return redirect(url_for("index"))

        success, output = run_conversion(output_format)
        converted, _skipped, failed = summarize_conversion_log(output)
        summary = f"{converted} converted to {output_format.upper()}, {failed} failed."
        flash(summary if success else f"Finished with errors. {summary}", "success" if success and not failed else "danger")
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
        if conversion_in_progress():
            return jsonify({"success": False, "message": BUSY_MESSAGE}), 409
        if not pending_conversions(output_format):
            return jsonify(
                {
                    "success": False,
                    "severity": "info",
                    "message": f"Everything is already converted to {output_format.upper()}.",
                }
            ), 409

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

        paths = [ALLOWED_CATEGORIES[category] / Path(item["name"]).name for item in files]
        return Response(
            stream_zip(paths),
            mimetype="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{category}.zip"'},
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
