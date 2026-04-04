import subprocess
from pathlib import Path

from ..config import DEFAULT_OUTPUT_FORMAT, OUTPUT_FORMATS, SCRIPT_PATH


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
    try:
        result = subprocess.run(
            [str(SCRIPT_PATH), normalized_format],
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

    try:
        process = subprocess.Popen(
            [str(SCRIPT_PATH), normalized_format],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd="/app",
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
        "message": f"Processing to {normalized_format.upper()} started.",
    }

    if process.stdout is not None:
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            collected_lines.append(line)
            line_event = parse_conversion_log_line(line)
            line_event["raw"] = line
            yield line_event

    return_code = process.wait()
    joined_output = "\n".join(collected_lines)
    converted, skipped, failed = summarize_conversion_log(joined_output)
    summary_message = (
        f"Processing to {normalized_format.upper()} finished. "
        f"{converted} converted, {skipped} skipped, {failed} failed."
    )
    if return_code != 0:
        summary_message = (
            f"Processing to {normalized_format.upper()} finished with errors. "
            f"{converted} converted, {skipped} skipped, {failed} failed."
        )

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
