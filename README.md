# Audio Exporter

A Dockerized Flask app for uploading audio or video files, validating that they contain an audio stream, and exporting the result as MP3 or FLAC with FFmpeg.

## Storage layout

Inside the container, all app data lives under `/songs`:

- `/songs/uploaded` - original uploaded media files
- `/songs/converted` - processed output files

In this repo, the mounted host folder is `songs/`.

## What it does

- Accepts audio files and video files that contain at least one audio stream.
- Rejects unsupported uploads before they are added to the queue.
- Lets the user choose the output format: MP3 or FLAC.
- Keeps original uploads in `uploaded` and writes converted files into `converted`.
- Supports individual downloads, deletion, and ZIP download for processed files.
- Shows upload and conversion activity in the web UI, including streamed conversion progress.
- Removes files older than six hours from both storage folders, with cleanup checks running hourly. Each file shows a retention tag: Active, Expiring (under 2h left) or Deleting (under 1h left, removed at the next sweep).
- Runs one conversion pass at a time; a pass keeps running if the browser tab is closed.

## Run with Docker Compose

```bash
docker compose up -d --build
```

The compose file mounts `./songs` on the host to `/songs` in the container and publishes the app at `http://localhost:7160`.

## Notes

- The app uses `/songs` inside the container (`AUDIO_EXPORTER_STORAGE_DIR`).
- Uploads are staged in `/songs/.incoming` until validated, so a conversion never picks up a half-written file.
- The app runs `fix_songs.sh` with `app/bin` first on `PATH`; `app/bin/ffmpeg` wraps the real ffmpeg with `-nostdin` so it cannot consume the script's file list.
- App source files live under `app/`.
- Output format defaults to MP3.
- `fix_songs.sh` handles the FFmpeg conversion work.
- `fix_songs.sh` retains embedded artwork by default when the input has attached cover art. Use `--drop-artwork` to disable that behavior for a run.
