# MP3 Fixer

A simple Dockerized Linux web app that accepts MP3 uploads, rebuilds them with FFmpeg, and lets you download original and fixed versions.

## What it does

- Accepts single or multiple `.mp3` uploads.
- Saves uploaded files into `/service/songs/uploaded`.
- Copies uploaded files into `/service/songs/old`.
- Rebuilds/fixes MP3 files with FFmpeg into `/service/songs/converted`.
- Provides downloads for individual files and ZIP archives for `old` and `converted`.

## Folder layout inside the container

- `/service/songs/uploaded` - original uploaded files as received by the web app.
- `/service/songs/old` - preserved working copies used as FFmpeg input.
- `/service/songs/converted` - rebuilt/fixed MP3 outputs.

## Important workflow rule

Uploaded files remain in `/service/songs/uploaded` and are not moved away. The shell script copies from `uploaded` to `old`, then uses the copy in `old` as FFmpeg input and writes output into `converted`.

## How uploads are handled

- Users upload `.mp3` files through the web UI.
- Filenames are sanitized to avoid unsafe characters and path traversal.
- If a filename already exists in `uploaded`, the app automatically creates a unique name like `song-2.mp3`.
- After upload, the app invokes the shell script to process uploaded files.

## How processing works

The shell script `/app/fix_songs.sh` does the actual conversion:

- Ensures `/service/songs/uploaded`, `/service/songs/old`, and `/service/songs/converted` exist.
- Scans `/service/songs/uploaded` for `.mp3` files.
- For each file:
  - copies it to `/service/songs/old`
  - runs `ffmpeg` against the copied file
  - writes the rebuilt file into `/service/songs/converted`
- Skips files already converted by default.
- Keeps the copy in `old` even when conversion fails.

### FFmpeg behavior

The script uses stream copy and writes the Xing header with flags equivalent to:

- `-map 0:a`
- `-c:a copy`
- `-write_xing 1`

## Downloads

- Individual files can be downloaded from any of the three categories: `uploaded`, `old`, and `converted`.
- ZIP archive downloads are available for `old` and `converted`.
- ZIP files are built dynamically from the current directory contents.

## How to build the Docker image

```bash
docker build -t mp3-fixer .
```

## How to run the container

```bash
docker run --rm -p 8000:8000 -v ~/service/songs:/service/songs mp3-fixer
```

## Notes

- The app always uses `/service/songs` inside the container.
- Do not rely on `~` inside the container; use absolute container paths.
- `uploaded` contains the originals.
- `old` contains preserved copies used for FFmpeg input.
- `converted` contains the rebuilt files.

The container also automatically clears MP3 files older than six hours from `uploaded`, `old`, and `converted` so the mounted storage remains clean.

## Files included

- `Dockerfile`
- `requirements.txt`
- `app.py`
- `fix_songs.sh`
- `templates/index.html`
- `static/style.css`
- `README.md`
