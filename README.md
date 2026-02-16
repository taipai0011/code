 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/README.md b/README.md
index b6ffa44da8a23998f8c3752aa75e3b70fb105ec6..66bc4707a6dd9056edc3490df43e8c37ff1e8691 100644
--- a/README.md
+++ b/README.md
@@ -1,2 +1,23 @@
-# code
-codes
+# Educational YouTube & Kling AI Downloader
+
+A Python website that accepts a YouTube or Kling AI URL and downloads content as MP4 or MP3.
+
+## Features
+
+- Interactive form with live platform detection (YouTube / Kling AI / Unknown).
+- URL and format validation with user-friendly error messages.
+- Download execution through `yt-dlp` with timeout handling.
+- Health endpoint: `GET /health`.
+
+## Important
+
+This is for educational use only. You are responsible for complying with platform terms and copyright laws.
+
+## Run locally
+
+```bash
+python3 -m pip install -r requirements.txt
+python3 app.py
+```
+
+Open: `http://localhost:5000`
diff --git a/app.py b/app.py
new file mode 100644
index 0000000000000000000000000000000000000000..60b8d8cbe6f5a725dc7f4df8c65b07a189f17d49
--- /dev/null
+++ b/app.py
@@ -0,0 +1,244 @@
+from __future__ import annotations
+
+import html
+import json
+import os
+import re
+import shutil
+import subprocess
+import tempfile
+from http import HTTPStatus
+from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
+from pathlib import Path
+from urllib.parse import parse_qs, urlparse
+
+HOST = "0.0.0.0"
+PORT = int(os.getenv("PORT", "5000"))
+MAX_FORM_BYTES = 8 * 1024
+URL_RE = re.compile(r"^https?://", re.IGNORECASE)
+STATIC_DIR = Path(__file__).parent / "static"
+
+
+def detect_platform(url: str) -> str:
+    """Return recognized platform name for a URL."""
+    lower = url.lower()
+    if "youtube.com" in lower or "youtu.be" in lower:
+        return "YouTube"
+    if "klingai" in lower or "kling.ai" in lower:
+        return "Kling AI"
+    return "Unknown"
+
+
+def is_valid_http_url(url: str) -> bool:
+    """Validate basic URL shape and accepted scheme."""
+    if not URL_RE.match(url):
+        return False
+    parsed = urlparse(url)
+    return bool(parsed.scheme in {"http", "https"} and parsed.netloc)
+
+
+def render_home(error: str = "", success: str = "") -> bytes:
+    escaped_error = html.escape(error)
+    escaped_success = html.escape(success)
+    error_block = f'<div class="alert error" role="alert">{escaped_error}</div>' if error else ""
+    success_block = f'<div class="alert success" role="status">{escaped_success}</div>' if success else ""
+
+    page = f"""<!doctype html>
+<html lang=\"en\">
+  <head>
+    <meta charset=\"UTF-8\" />
+    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
+    <title>Educational Video Downloader</title>
+    <link rel=\"stylesheet\" href=\"/static/style.css\" />
+    <script defer src=\"/static/app.js\"></script>
+  </head>
+  <body>
+    <main class=\"card\">
+      <h1>YouTube & Kling AI Downloader</h1>
+      <p class=\"note\">This tool is for <strong>educational purposes only</strong>. Download only content you own or have explicit permission to use.</p>
+      {error_block}
+      {success_block}
+      <form action=\"/download\" method=\"post\" id=\"download-form\">
+        <label for=\"url\">Video URL</label>
+        <input id=\"url\" name=\"url\" type=\"url\" placeholder=\"https://www.youtube.com/watch?v=...\" required />
+        <small id=\"platform-preview\" class=\"hint\">Detected platform: waiting for URL…</small>
+
+        <label for=\"format\">Download format</label>
+        <select id=\"format\" name=\"format\">
+          <option value=\"mp4\">MP4 (video)</option>
+          <option value=\"mp3\">MP3 (audio only)</option>
+        </select>
+
+        <button type=\"submit\" id=\"submit-btn\">Download</button>
+      </form>
+    </main>
+  </body>
+</html>
+"""
+    return page.encode("utf-8")
+
+
+class AppHandler(BaseHTTPRequestHandler):
+    protocol_version = "HTTP/1.1"
+
+    def do_GET(self) -> None:
+        try:
+            path = urlparse(self.path).path
+            if path == "/":
+                self.respond_html(HTTPStatus.OK, render_home())
+                return
+
+            if path == "/health":
+                self.respond_json(HTTPStatus.OK, {"status": "ok"})
+                return
+
+            if path == "/static/style.css":
+                self.serve_static_file("style.css", "text/css; charset=utf-8")
+                return
+
+            if path == "/static/app.js":
+                self.serve_static_file("app.js", "application/javascript; charset=utf-8")
+                return
+
+            self.send_error(HTTPStatus.NOT_FOUND)
+        except Exception:
+            self.respond_html(HTTPStatus.INTERNAL_SERVER_ERROR, render_home("Unexpected server error."))
+
+    def do_POST(self) -> None:
+        try:
+            path = urlparse(self.path).path
+            if path != "/download":
+                self.send_error(HTTPStatus.NOT_FOUND)
+                return
+
+            content_length = int(self.headers.get("Content-Length", "0"))
+            if content_length <= 0 or content_length > MAX_FORM_BYTES:
+                self.respond_form_error("Request is too large or invalid.", status=HTTPStatus.BAD_REQUEST)
+                return
+
+            raw = self.rfile.read(content_length)
+            form = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
+
+            url = (form.get("url") or [""])[0].strip()
+            output_format = ((form.get("format") or ["mp4"])[0].strip().lower())
+
+            if not url or not is_valid_http_url(url):
+                self.respond_form_error("Please provide a valid http/https URL.")
+                return
+
+            if output_format not in {"mp4", "mp3"}:
+                self.respond_form_error("Invalid format selected.")
+                return
+
+            if detect_platform(url) == "Unknown":
+                self.respond_form_error("Only YouTube and Kling AI URLs are allowed in this educational demo.")
+                return
+
+            yt_dlp = shutil.which("yt-dlp")
+            if not yt_dlp:
+                self.respond_form_error("yt-dlp is not installed on this server.", status=HTTPStatus.SERVICE_UNAVAILABLE)
+                return
+
+            self.handle_download(url, output_format, yt_dlp)
+        except Exception:
+            self.respond_form_error("Unexpected server error. Please try again.", status=HTTPStatus.INTERNAL_SERVER_ERROR)
+
+    def do_HEAD(self) -> None:
+        path = urlparse(self.path).path
+        if path == "/health":
+            payload = json.dumps({"status": "ok"}).encode("utf-8")
+            self.send_response(HTTPStatus.OK)
+            self.send_header("Content-Type", "application/json")
+            self.send_header("Content-Length", str(len(payload)))
+            self.end_headers()
+            return
+        self.send_error(HTTPStatus.NOT_FOUND)
+
+    def serve_static_file(self, filename: str, content_type: str) -> None:
+        file_path = STATIC_DIR / filename
+        if not file_path.exists() or not file_path.is_file():
+            self.send_error(HTTPStatus.NOT_FOUND)
+            return
+
+        data = file_path.read_bytes()
+        self.send_response(HTTPStatus.OK)
+        self.send_header("Content-Type", content_type)
+        self.send_header("Content-Length", str(len(data)))
+        self.end_headers()
+        self.wfile.write(data)
+
+    def handle_download(self, url: str, output_format: str, yt_dlp: str) -> None:
+        temp_dir = tempfile.mkdtemp(prefix="edu_downloader_")
+        try:
+            output_template = str(Path(temp_dir) / "downloaded.%(ext)s")
+            if output_format == "mp3":
+                cmd = [yt_dlp, "--no-playlist", "-x", "--audio-format", "mp3", "-o", output_template, url]
+                mime = "audio/mpeg"
+                filename = "downloaded.mp3"
+            else:
+                cmd = [
+                    yt_dlp,
+                    "--no-playlist",
+                    "-f",
+                    "mp4/bestvideo+bestaudio/best",
+                    "--merge-output-format",
+                    "mp4",
+                    "-o",
+                    output_template,
+                    url,
+                ]
+                mime = "video/mp4"
+                filename = "downloaded.mp4"
+
+            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
+            if result.returncode != 0:
+                self.respond_form_error("Download failed. URL may be invalid, restricted, or blocked.")
+                return
+
+            generated = sorted(Path(temp_dir).glob("downloaded.*"))
+            if not generated:
+                self.respond_form_error("No file was produced by downloader.")
+                return
+
+            file_path = generated[0]
+            file_size = file_path.stat().st_size
+
+            self.send_response(HTTPStatus.OK)
+            self.send_header("Content-Type", mime)
+            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
+            self.send_header("Content-Length", str(file_size))
+            self.end_headers()
+
+            with file_path.open("rb") as output_file:
+                shutil.copyfileobj(output_file, self.wfile)
+        except subprocess.TimeoutExpired:
+            self.respond_form_error("Download timed out. Please try a shorter or different video.", status=HTTPStatus.REQUEST_TIMEOUT)
+        finally:
+            shutil.rmtree(temp_dir, ignore_errors=True)
+
+    def respond_html(self, status: HTTPStatus, body: bytes) -> None:
+        self.send_response(status)
+        self.send_header("Content-Type", "text/html; charset=utf-8")
+        self.send_header("Content-Length", str(len(body)))
+        self.end_headers()
+        self.wfile.write(body)
+
+    def respond_json(self, status: HTTPStatus, payload: dict[str, str]) -> None:
+        body = json.dumps(payload).encode("utf-8")
+        self.send_response(status)
+        self.send_header("Content-Type", "application/json; charset=utf-8")
+        self.send_header("Content-Length", str(len(body)))
+        self.end_headers()
+        self.wfile.write(body)
+
+    def respond_form_error(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
+        self.respond_html(status, render_home(error=message))
+
+    def log_message(self, format: str, *args: object) -> None:
+        return
+
+
+if __name__ == "__main__":
+    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
+    print(f"Server running at http://{HOST}:{PORT}")
+    server.serve_forever()
diff --git a/requirements.txt b/requirements.txt
new file mode 100644
index 0000000000000000000000000000000000000000..0cc04d1ffe42c0a3bd8fb30a0f17fe7227b29965
--- /dev/null
+++ b/requirements.txt
@@ -0,0 +1 @@
+yt-dlp>=2024.8.6
diff --git a/static/app.js b/static/app.js
new file mode 100644
index 0000000000000000000000000000000000000000..27dbe11fd9b726cf453d43d97c37be030d36d666
--- /dev/null
+++ b/static/app.js
@@ -0,0 +1,42 @@
+(function () {
+  const form = document.getElementById('download-form');
+  const urlInput = document.getElementById('url');
+  const submitBtn = document.getElementById('submit-btn');
+  const platformPreview = document.getElementById('platform-preview');
+
+  if (!form || !urlInput || !submitBtn || !platformPreview) {
+    return;
+  }
+
+  function detectPlatform(url) {
+    const lower = String(url || '').toLowerCase();
+    if (lower.includes('youtube.com') || lower.includes('youtu.be')) {
+      return 'YouTube';
+    }
+    if (lower.includes('kling.ai') || lower.includes('klingai')) {
+      return 'Kling AI';
+    }
+    return 'Unknown';
+  }
+
+  function updatePlatformHint() {
+    const value = urlInput.value.trim();
+    if (!value) {
+      platformPreview.textContent = 'Detected platform: waiting for URL…';
+      platformPreview.className = 'hint';
+      return;
+    }
+
+    const platform = detectPlatform(value);
+    platformPreview.textContent = `Detected platform: ${platform}`;
+    platformPreview.className = platform === 'Unknown' ? 'hint error-text' : 'hint success-text';
+  }
+
+  urlInput.addEventListener('input', updatePlatformHint);
+  updatePlatformHint();
+
+  form.addEventListener('submit', function () {
+    submitBtn.disabled = true;
+    submitBtn.textContent = 'Preparing download...';
+  });
+})();
diff --git a/static/style.css b/static/style.css
new file mode 100644
index 0000000000000000000000000000000000000000..97469a884195166f97197d5a27d8176367261162
--- /dev/null
+++ b/static/style.css
@@ -0,0 +1,99 @@
+:root {
+  color-scheme: light dark;
+  font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
+}
+
+body {
+  margin: 0;
+  min-height: 100vh;
+  display: grid;
+  place-items: center;
+  background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
+}
+
+.card {
+  width: min(92vw, 560px);
+  background: rgba(255, 255, 255, 0.95);
+  color: #0f172a;
+  border-radius: 16px;
+  padding: 1.2rem 1.4rem;
+  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.22);
+}
+
+h1 {
+  margin-top: 0;
+  margin-bottom: 0.7rem;
+  font-size: 1.4rem;
+}
+
+.note {
+  font-size: 0.95rem;
+  margin: 0 0 1rem;
+}
+
+.alert {
+  border-radius: 10px;
+  padding: 0.7rem;
+  margin-bottom: 1rem;
+}
+
+.error {
+  background: #fee2e2;
+  border: 1px solid #ef4444;
+  color: #991b1b;
+}
+
+.success {
+  background: #dcfce7;
+  border: 1px solid #22c55e;
+  color: #166534;
+}
+
+form {
+  display: grid;
+  gap: 0.55rem;
+}
+
+label {
+  font-weight: 600;
+}
+
+.hint {
+  margin-top: -0.3rem;
+  margin-bottom: 0.3rem;
+  color: #475569;
+}
+
+.error-text {
+  color: #b91c1c;
+}
+
+.success-text {
+  color: #166534;
+}
+
+input,
+select,
+button {
+  font: inherit;
+  border-radius: 10px;
+  border: 1px solid #cbd5e1;
+  padding: 0.65rem 0.75rem;
+}
+
+button {
+  border: 0;
+  color: white;
+  font-weight: 700;
+  background: #2563eb;
+  cursor: pointer;
+}
+
+button:hover {
+  background: #1d4ed8;
+}
+
+button:disabled {
+  opacity: 0.7;
+  cursor: progress;
+}
diff --git a/tests/test_app.py b/tests/test_app.py
new file mode 100644
index 0000000000000000000000000000000000000000..12809d7a62048bd64b8fa83bed4a56846dd151ca
--- /dev/null
+++ b/tests/test_app.py
@@ -0,0 +1,23 @@
+import unittest
+
+import app
+
+
+class TestAppHelpers(unittest.TestCase):
+    def test_detect_platform_youtube(self):
+        self.assertEqual(app.detect_platform('https://youtube.com/watch?v=abc'), 'YouTube')
+
+    def test_detect_platform_kling(self):
+        self.assertEqual(app.detect_platform('https://kling.ai/some/video'), 'Kling AI')
+
+    def test_detect_platform_unknown(self):
+        self.assertEqual(app.detect_platform('https://example.com/video'), 'Unknown')
+
+    def test_url_validation(self):
+        self.assertTrue(app.is_valid_http_url('https://youtube.com/watch?v=abc'))
+        self.assertFalse(app.is_valid_http_url('ftp://youtube.com/watch?v=abc'))
+        self.assertFalse(app.is_valid_http_url('not-a-url'))
+
+
+if __name__ == '__main__':
+    unittest.main()
 
EOF
)
