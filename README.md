# Audio Fixer

A small Dockerized Flask app that accepts media uploads, extracts the first audio stream with FFmpeg, and writes processed output as MP3 or FLAC. 

## Storage layout

Inside the container, all app data lives under `/songs`:

- `/songs/uploaded` - original uploaded media files
- `/songs/converted` - processed output files

In this repo, the mounted host folder is `songs/`.

## What it does

- Accepts audio files and video files that contain at least one audio stream.
- Lets the user choose the output format: MP3 or FLAC.
- Keeps original uploads in `uploaded` and writes processed files into `converted`.
- Provides individual downloads for uploaded and processed files.
- Provides ZIP download for processed files.
- Cleans up files older than six hours from both storage folders.

## Run with Docker Compose

```bash
docker compose up --build
```

The compose file mounts `./songs` on the host to `/songs` in the container.

## Run with Docker directly

```bash
docker build -t mp3-fixer .
docker run --rm -p 8000:8000 -v ~/songs:/songs mp3-fixer
```

## Notes

- The app uses `/songs` inside the container.
- Output format defaults to MP3.
- `fix_songs.sh` handles the FFmpeg conversion work.
