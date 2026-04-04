FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY app/ ./

RUN chmod +x /app/fix_songs.sh

ENV PYTHONUNBUFFERED=1 \
    AUDIO_EXPORTER_STORAGE_DIR=/songs \
    AUDIO_EXPORTER_SCRIPT_PATH=/app/fix_songs.sh
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app", "--workers", "1", "--threads", "2"]
