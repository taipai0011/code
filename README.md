# Educational YouTube & Kling AI Downloader

A Python website that accepts a YouTube or Kling AI URL and downloads content as MP4 or MP3.

## Features

- Interactive form with live platform detection (YouTube / Kling AI / Unknown).
- URL and format validation with user-friendly error messages.
- Download execution through `yt-dlp` with timeout handling.
- Health endpoint: `GET /health`.

## Important

This is for educational use only. You are responsible for complying with platform terms and copyright laws.

## Run locally

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

Open: `http://localhost:5000`
