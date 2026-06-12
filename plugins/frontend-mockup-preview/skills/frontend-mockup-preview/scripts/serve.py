#!/usr/bin/env python3
"""Self-contained live-reload static server (Python stdlib only).

Serves a directory over HTTP and auto-refreshes connected browsers whenever any
file in that directory changes. No external dependencies and no `npm install` —
it uses Server-Sent Events plus mtime polling, so it works even with no network.

This exists so the mockup-preview loop is frictionless: the agent edits the
mockup HTML in response to user feedback, and the user's browser refreshes on
its own. The user never has to reload.

Usage:
    python3 serve.py <directory> [--port 8765] [--host 0.0.0.0]
"""
import argparse
import http.server
import os
import socket
import socketserver
import sys
import time
from pathlib import Path

# Injected before </body> of every HTML response. Opens an SSE channel and
# reloads the page when the server signals a change. Wrapped in try/catch so a
# mockup never breaks just because live-reload hiccups.
RELOAD_SNIPPET = b"""
<script>
(function(){
  try {
    var es = new EventSource("/__livereload");
    es.onmessage = function(e){ if (e.data === "reload") location.reload(); };
  } catch (err) {}
})();
</script>
"""


def snapshot(root):
    """Map of file path -> mtime for everything under root. Comparing two
    snapshots tells us if anything changed, added, or was removed."""
    sig = {}
    for p in Path(root).rglob("*"):
        if p.is_file():
            try:
                sig[str(p)] = p.stat().st_mtime
            except OSError:
                pass
    return sig


def make_handler(root):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(root), **k)

        def log_message(self, *a):  # keep the console quiet
            pass

        def do_GET(self):
            if self.path == "/__livereload":
                self._serve_sse()
                return

            path = self.translate_path(self.path)
            if os.path.isdir(path):
                index = os.path.join(path, "index.html")
                if os.path.exists(index):
                    path = index

            if path.endswith(".html") and os.path.exists(path):
                self._serve_html(path)
                return

            super().do_GET()

        def _serve_html(self, path):
            with open(path, "rb") as f:
                body = f.read()
            if b"</body>" in body:
                body = body.replace(b"</body>", RELOAD_SNIPPET + b"</body>", 1)
            else:
                body += RELOAD_SNIPPET
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _serve_sse(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            last = snapshot(root)
            try:
                while True:
                    time.sleep(0.5)
                    cur = snapshot(root)
                    if cur != last:
                        last = cur
                        self.wfile.write(b"data: reload\n\n")
                    else:
                        self.wfile.write(b": ping\n\n")  # keepalive
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

    return Handler


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    # Threaded so the long-lived SSE connection doesn't block normal requests.
    daemon_threads = True
    allow_reuse_address = True


def find_free_port(host, preferred, attempts=50):
    """Return a bindable port, starting at `preferred` and walking up. Avoids the
    manual 'port busy, try the next one' dance — the script just picks one."""
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise SystemExit(f"mockup-preview: no free port in {preferred}-{preferred + attempts}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()

    root = Path(args.directory).resolve()
    root.mkdir(parents=True, exist_ok=True)

    port = find_free_port(args.host, args.port)
    httpd = ThreadingServer((args.host, port), make_handler(root))
    # Machine-readable line so the launcher can grep the actual URL/PID reliably.
    print(f"MOCKUP_PREVIEW_URL=http://localhost:{port}/")
    print(f"MOCKUP_PREVIEW_PID={os.getpid()}")
    print(f"mockup-preview: serving {root}")
    print(f"mockup-preview: open http://localhost:{port}/ (live-reload on)")
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
