import subprocess

from ..config import SCRIPT_PATH


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
