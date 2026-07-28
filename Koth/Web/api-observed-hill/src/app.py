"""Shared KotH hill whose controller is sampled by an external observer."""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


MAX_REQUEST_BYTES = 512
MAX_TOKEN_BYTES = 256
BANNER = "rsctf KotH API demo: POST your token to /claim"
state_lock = threading.Lock()
controller_token: str | None = None


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _text(self, status: int, text: str) -> None:
        self._send(status, text.encode(), "text/plain; charset=utf-8")

    def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        request = urlsplit(self.path)
        if request.query:
            self._text(400, "query parameters are not accepted\n")
            return
        if request.path == "/health":
            self._text(200, "ok\n")
            return
        if request.path == "/":
            self._text(200, f"{BANNER}\n")
            return
        if request.path == "/control":
            with state_lock:
                token = controller_token
            body = json.dumps(
                {"token": token},
                separators=(",", ":"),
            ).encode()
            self._send(200, body, "application/json")
            return
        self._text(404, "not found\n")

    def do_POST(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        global controller_token

        request = urlsplit(self.path)
        if request.path != "/claim" or request.query:
            self._text(404, "not found\n")
            return
        media_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if media_type != "application/x-www-form-urlencoded":
            self._text(415, "use application/x-www-form-urlencoded\n")
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._text(400, "invalid content length\n")
            return
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._text(413, "invalid request size\n")
            return
        try:
            form = parse_qs(
                self.rfile.read(length).decode("utf-8"),
                keep_blank_values=True,
                strict_parsing=True,
            )
        except (UnicodeDecodeError, ValueError):
            self._text(400, "invalid form body\n")
            return
        values = form.get("token", [])
        token = values[0] if len(values) == 1 and len(form) == 1 else ""
        if (
            not token
            or len(token.encode()) > MAX_TOKEN_BYTES
            or "\n" in token
            or "\r" in token
        ):
            self._text(400, "invalid token\n")
            return
        with state_lock:
            controller_token = token
        self._text(200, "claim recorded\n")

    def log_message(self, _format, *_args):
        # Do not put team capabilities into default HTTP access logs.
        pass


port = int(os.environ.get("PORT", "8080"))
ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
