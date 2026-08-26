"""Intentionally vulnerable self-hosted (BYOC) A&D service.

The rsctf BYOC agent atomically refreshes RSCTF_FLAG_FILE every round. Reading
that file per request is the service-side contract; RSCTF_FLAG is not suitable
because a container environment cannot change after startup.
"""

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


FLAG_FILE = Path(os.environ.get("RSCTF_FLAG_FILE", "/run/rsctf/flag"))


def read_current_flag() -> str:
    try:
        return FLAG_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "flag-not-delivered-yet"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        path = urlsplit(self.path).path
        status = 200
        if path == "/health":
            body = b"ok\n"
        elif path == "/secret":
            body = (read_current_flag() + "\n").encode()
        elif path == "/":
            body = b"rsctf BYOC demo: find the vulnerable /secret endpoint\n"
        else:
            status = 404
            body = b"not found\n"

        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        pass


port = int(os.environ.get("PORT", "8080"))
ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
