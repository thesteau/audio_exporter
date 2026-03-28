#!/usr/bin/env bash
set -uo pipefail
IFS=$'\n\t'

OUTPUT_FORMAT="${1:-mp3}"
case "$OUTPUT_FORMAT" in
  mp3|flac)
    ;;
  *)
    echo "Unsupported output format: $OUTPUT_FORMAT" >&2
    exit 1
    ;;
esac

BASE_DIR="/songs"
UPLOADED_DIR="$BASE_DIR/uploaded"
CONVERTED_DIR="$BASE_DIR/converted"

KNOWN_EXTENSIONS=(.mp3 .flac .wav .aac .m4a .ogg .opus .wma .aiff .aif .alac .mp4 .m4v .mov .mkv .avi .webm .wmv .flv .mpeg .mpg)

mkdir -p "$UPLOADED_DIR" "$CONVERTED_DIR"

strip_known_extensions() {
  local base_name="$1"
  local lower_name extension removed

  while true; do
    lower_name="${base_name,,}"
    removed=0
    for extension in "${KNOWN_EXTENSIONS[@]}"; do
      if [[ "$lower_name" == *"$extension" ]]; then
        base_name="${base_name%.*}"
        removed=1
        break
      fi
    done
    if [ "$removed" -eq 0 ]; then
      printf '%s\n' "$base_name"
      return
    fi
  done
}

build_converted_name() {
  local input_name="$1"
  local base_name

  base_name="$(strip_known_extensions "$input_name")"
  if [ -z "$base_name" ]; then
    base_name="converted"
  fi
  printf '%s.%s\n' "$base_name" "$OUTPUT_FORMAT"
}

detect_audio_codec() {
  ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$1" | head -n 1
}

echo "Starting media conversion pass to $OUTPUT_FORMAT..."
find "$UPLOADED_DIR" -maxdepth 1 -type f | sort | while IFS= read -r source_file; do
  file_name="$(basename "$source_file")"
  converted_name="$(build_converted_name "$file_name")"
  dest_converted="$CONVERTED_DIR/$converted_name"

  if [ -f "$dest_converted" ]; then
    echo "Skipping already converted: $file_name"
    continue
  fi

  echo "Fixing: $file_name -> $converted_name"

  codec_name="$(detect_audio_codec "$source_file")"
  if [ -z "$codec_name" ]; then
    echo "Failed conversion: $file_name" >&2
    continue
  fi

  if [ "$OUTPUT_FORMAT" = "mp3" ]; then
    if [ "$codec_name" = "mp3" ]; then
      ffmpeg_args=(-hide_banner -loglevel error -y -i "$source_file" -map 0:a:0 -c:a copy -write_xing 1 "$dest_converted")
    else
      ffmpeg_args=(-hide_banner -loglevel error -y -i "$source_file" -map 0:a:0 -c:a libmp3lame -q:a 2 -write_xing 1 "$dest_converted")
    fi
  else
    if [ "$codec_name" = "flac" ]; then
      ffmpeg_args=(-hide_banner -loglevel error -y -i "$source_file" -map 0:a:0 -c:a copy "$dest_converted")
    else
      ffmpeg_args=(-hide_banner -loglevel error -y -i "$source_file" -map 0:a:0 -c:a flac "$dest_converted")
    fi
  fi

  if ffmpeg "${ffmpeg_args[@]}"; then
    echo "Converted successfully: $file_name"
  else
    rm -f "$dest_converted"
    echo "Failed conversion: $file_name" >&2
  fi

done

echo "Media conversion pass finished."
