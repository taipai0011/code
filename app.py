from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "5000"))
MAX_FORM_BYTES = 8 * 1024
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
STATIC_DIR = Path(__file__).parent / "static"


def detect_platform(url: str) -> str:
    """Return recognized platform name for a URL."""
    lower = url.lower()
    if "youtube.com" in lower or "youtu.be" in lower:
        return "YouTube"
    if "klingai" in lower or "kling.ai" in lower:
        return "Kling AI"
    return "Unknown"


def is_valid_http_url(url: str) -> bool:
    """Validate basic URL shape and accepted scheme."""
    if not URL_RE.match(url):
        return False
    parsed = urlparse(url)
    return bool(parsed.scheme in {"http", "https"} and parsed.netloc)


def render_home(error: str = "", success: str = "") -> bytes:
    escaped_error = html.escape(error)
    escaped_success = html.escape(success)
    error_block = f'<div class="alert error" role="alert">{escaped_error}</div>' if error else ""
    success_block = f'<div class="alert success" role="status">{escaped_success}</div>' if success else ""

    page = f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>Educational Video Downloader</title>
    <link rel=\"stylesheet\" href=\"/static/style.css\" />
    <script defer src=\"/static/app.js\"></script>
  </head>
  <body>
    <main class=\"card\">
      <h1>YouTube & Kling AI Downloader</h1>
      <p class=\"note\">This tool is for <strong>educational purposes only</strong>. Download only content you own or have explicit permission to use.</p>
      {error_block}
      {success_block}
      <form action=\"/download\" method=\"post\" id=\"download-form\">
        <label for=\"url\">Video URL</label>
        <input id=\"url\" name=\"url\" type=\"url\" placeholder=\"https://www.youtube.com/watch?v=...\" required />
        <small id=\"platform-preview\" class=\"hint\">Detected platform: waiting for URL…</small>

        <label for=\"format\">Download format</label>
        <select id=\"format\" name=\"format\">
          <option value=\"mp4\">MP4 (video)</option>
          <option value=\"mp3\">MP3 (audio only)</option>
        </select>

        <button type=\"submit\" id=\"submit-btn\">Download</button>
      </form>
    </main>
  </body>
</html>
"""
    return page.encode("utf-8")


class AppHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/":
                self.respond_html(HTTPStatus.OK, render_home())
                return

            if path == "/health":
                self.respond_json(HTTPStatus.OK, {"status": "ok"})
                return

            if path == "/static/style.css":
                self.serve_static_file("style.css", "text/css; charset=utf-8")
                return

            if path == "/static/app.js":
                self.serve_static_file("app.js", "application/javascript; charset=utf-8")
                return

            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception:
            self.respond_html(HTTPStatus.INTERNAL_SERVER_ERROR, render_home("Unexpected server error."))

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            if path != "/download":
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_FORM_BYTES:
                self.respond_form_error("Request is too large or invalid.", status=HTTPStatus.BAD_REQUEST)
                return

            raw = self.rfile.read(content_length)
            form = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)

            url = (form.get("url") or [""])[0].strip()
            output_format = ((form.get("format") or ["mp4"])[0].strip().lower())

            if not url or not is_valid_http_url(url):
                self.respond_form_error("Please provide a valid http/https URL.")
                return

            if output_format not in {"mp4", "mp3"}:
                self.respond_form_error("Invalid format selected.")
                return

            if detect_platform(url) == "Unknown":
                self.respond_form_error("Only YouTube and Kling AI URLs are allowed in this educational demo.")
                return

            yt_dlp = shutil.which("yt-dlp")
            if not yt_dlp:
                self.respond_form_error("yt-dlp is not installed on this server.", status=HTTPStatus.SERVICE_UNAVAILABLE)
                return

            self.handle_download(url, output_format, yt_dlp)
        except Exception:
            self.respond_form_error("Unexpected server error. Please try again.", status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_HEAD(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            payload = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def serve_static_file(self, filename: str, content_type: str) -> None:
        file_path = STATIC_DIR / filename
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_download(self, url: str, output_format: str, yt_dlp: str) -> None:
        temp_dir = tempfile.mkdtemp(prefix="edu_downloader_")
        try:
            output_template = str(Path(temp_dir) / "downloaded.%(ext)s")
            if output_format == "mp3":
                cmd = [yt_dlp, "--no-playlist", "-x", "--audio-format", "mp3", "-o", output_template, url]
                mime = "audio/mpeg"
                filename = "downloaded.mp3"
            else:
                cmd = [
                    yt_dlp,
                    "--no-playlist",
                    "-f",
                    "mp4/bestvideo+bestaudio/best",
                    "--merge-output-format",
                    "mp4",
                    "-o",
                    output_template,
                    url,
                ]
                mime = "video/mp4"
                filename = "downloaded.mp4"

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                self.respond_form_error("Download failed. URL may be invalid, restricted, or blocked.")
                return

            generated = sorted(Path(temp_dir).glob("downloaded.*"))
            if not generated:
                self.respond_form_error("No file was produced by downloader.")
                return

            file_path = generated[0]
            file_size = file_path.stat().st_size

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(file_size))
            self.end_headers()

            with file_path.open("rb") as output_file:
                shutil.copyfileobj(output_file, self.wfile)
        except subprocess.TimeoutExpired:
            self.respond_form_error("Download timed out. Please try a shorter or different video.", status=HTTPStatus.REQUEST_TIMEOUT)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def respond_html(self, status: HTTPStatus, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_json(self, status: HTTPStatus, payload: dict[str, str]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_form_error(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        self.respond_html(status, render_home(error=message))

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Server running at http://{HOST}:{PORT}")
    server.serve_forever()
