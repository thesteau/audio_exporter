#!/usr/bin/env bash
set -uo pipefail
IFS=$'\n\t'

BASE_DIR="/service/songs"
UPLOADED_DIR="$BASE_DIR/uploaded"
OLD_DIR="$BASE_DIR/old"
CONVERTED_DIR="$BASE_DIR/converted"

mkdir -p "$UPLOADED_DIR" "$OLD_DIR" "$CONVERTED_DIR"

echo "Starting MP3 fix pass..."
find "$UPLOADED_DIR" -maxdepth 1 -type f \( -iname '*.mp3' \) | sort | while IFS= read -r source_file; do
  file_name="$(basename "$source_file")"
  dest_old="$OLD_DIR/$file_name"
  dest_converted="$CONVERTED_DIR/$file_name"

  if [ -f "$dest_old" ]; then
    echo "Skipping already converted: $file_name"
    continue
  fi

  echo "Fixing: $file_name"

  if ! mv -- "$source_file" "$dest_old"; then
    echo "Failed conversion: $file_name" >&2
    continue
  fi

  if ffmpeg -hide_banner -loglevel error -y -i "$dest_old" -map 0:a -c:a copy -write_xing 1 "$dest_converted"; then
    echo "Converted successfully: $file_name"
  else
    rm -f "$dest_converted"
    mv -- "$dest_old" "$source_file"
    echo "Failed conversion: $file_name" >&2
  fi

done

echo "MP3 fix pass finished."
