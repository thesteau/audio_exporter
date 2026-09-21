import os
import shutil
import subprocess
import threading
from pathlib import Path

from ..config import DEFAULT_OUTPUT_FORMAT, GUARD_BIN_DIR, OUTPUT_FORMATS, PROJECT_ROOT, SCRIPT_PATH
from .files import pending_conversions

# Only one conversion pass at a time: concurrent passes would write the same outputs.
_conversion_lock = threading.Lock()
BUSY_MESSAGE = "A conversion is already running. Wait for it to finish."


def conversion_in_progress() -> bool:
    return _conversion_lock.locked()


def _conversion_env():
    # bin/ffmpeg wraps the real ffmpeg with -nostdin so fix_songs.sh's read loop keeps its input.
    return {**os.environ, "PATH": f"{GUARD_BIN_DIR}{os.pathsep}{os.environ.get('PATH', '')}"}


def _finish_in_background(process: subprocess.Popen):
    """Keep a pass running after the client disconnects, then release the lock."""
    try:
        if process.stdout is not None:
            for _ in process.stdout:
                pass
        process.wait()
    finally:
        _conversion_lock.release()


def normalize_output_format(output_format: str | None) -> str:
    if not output_format:
        return DEFAULT_OUTPUT_FORMAT
    normalized = output_format.lower()
    if normalized in OUTPUT_FORMATS:
        return normalized
    return DEFAULT_OUTPUT_FORMAT


def media_file_has_audio(file_path: Path) -> bool:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0 and result.stdout.strip() == "audio"


def run_conversion(output_format: str = DEFAULT_OUTPUT_FORMAT):
    normalized_format = normalize_output_format(output_format)
    if not SCRIPT_PATH.exists():
        return False, "Conversion script not found."
    if not _conversion_lock.acquire(blocking=False):
        return False, BUSY_MESSAGE
    try:
        result = subprocess.run(
            build_conversion_command(normalized_format),
            capture_output=True,
            text=True,
            check=False,
            cwd=str(PROJECT_ROOT),
            env=_conversion_env(),
        )
    except Exception as exc:
        return False, f"Conversion execution failure: {exc}"
    finally:
        _conversion_lock.release()

    output = result.stdout.strip()
    if result.stderr.strip():
        output = f"{output}\n{result.stderr.strip()}" if output else result.stderr.strip()
    return result.returncode == 0, output


def stream_conversion_events(output_format: str = DEFAULT_OUTPUT_FORMAT):
    normalized_format = normalize_output_format(output_format)
    if not SCRIPT_PATH.exists():
        yield {
            "event": "error",
            "message": "Conversion script not found.",
        }
        yield {
            "event": "complete",
            "success": False,
            "converted": 0,
            "skipped": 0,
            "failed": 0,
            "output_format": normalized_format,
            "message": "Processing could not start because the conversion script was not found.",
        }
        return

    if not _conversion_lock.acquire(blocking=False):
        yield {"event": "error", "message": BUSY_MESSAGE}
        yield {
            "event": "complete",
            "success": False,
            "converted": 0,
            "skipped": 0,
            "failed": 0,
            "output_format": normalized_format,
            "message": BUSY_MESSAGE,
        }
        return

    # Computed under the lock, so it matches what this pass will actually convert.
    planned_files = pending_conversions(normalized_format)
    process = None
    try:
        try:
            process = subprocess.Popen(
                build_conversion_command(normalized_format),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                cwd=str(PROJECT_ROOT),
                env=_conversion_env(),
            )
        except Exception as exc:
            yield {
                "event": "error",
                "message": f"Conversion execution failure: {exc}",
            }
            yield {
                "event": "complete",
                "success": False,
                "converted": 0,
                "skipped": 0,
                "failed": 0,
                "output_format": normalized_format,
                "message": f"Processing could not start: {exc}",
            }
            return

        collected_lines = []
        yield {
            "event": "start",
            "output_format": normalized_format,
            "files": planned_files,
            "message": f"Processing to {normalized_format.upper()} started.",
        }

        if process.stdout is not None:
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                collected_lines.append(line)
                line_event = parse_conversion_log_line(line)
                # Files that already have an output are not news; keep them out of the UI.
                if line_event.get("status") == "skipped":
                    continue
                line_event["raw"] = line
                yield line_event

        return_code = process.wait()
    finally:
        if process is not None and process.poll() is None:
            # Client went away mid-pass (tab closed, refresh): let the pass finish.
            threading.Thread(target=_finish_in_background, args=(process,), daemon=True).start()
        else:
            _conversion_lock.release()

    joined_output = "\n".join(collected_lines)
    converted, skipped, failed = summarize_conversion_log(joined_output)
    summary_message = f"{converted} converted to {normalized_format.upper()}."
    if failed:
        summary_message = f"{summary_message[:-1]}, {failed} failed."
    if return_code != 0:
        summary_message = f"Finished with errors. {summary_message}"

    yield {
        "event": "complete",
        "success": return_code == 0,
        "converted": converted,
        "skipped": skipped,
        "failed": failed,
        "output_format": normalized_format,
        "message": summary_message,
    }


def parse_conversion_log_line(line: str):
    if line.startswith("Fixing: "):
        details = line.removeprefix("Fixing: ")
        source_name, separator, output_name = details.partition(" -> ")
        return {
            "event": "file",
            "status": "processing",
            "source_name": source_name,
            "output_name": output_name if separator else "",
            "message": line,
        }

    if line.startswith("Converted successfully: "):
        return {
            "event": "file",
            "status": "success",
            "source_name": line.removeprefix("Converted successfully: "),
            "message": line,
        }

    if line.startswith("Skipping already converted: "):
        return {
            "event": "file",
            "status": "skipped",
            "source_name": line.removeprefix("Skipping already converted: "),
            "message": line,
        }

    if line.startswith("Failed conversion: "):
        return {
            "event": "file",
            "status": "error",
            "source_name": line.removeprefix("Failed conversion: "),
            "message": line,
        }

    return {
        "event": "log",
        "message": line,
    }


def build_conversion_command(output_format: str):
    bash_path = shutil.which("bash")
    if bash_path:
        return [bash_path, str(SCRIPT_PATH), output_format]
    return [str(SCRIPT_PATH), output_format]


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
