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
