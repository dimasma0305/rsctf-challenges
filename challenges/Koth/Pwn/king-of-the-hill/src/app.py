"""Small shared KotH hill implementing rsctf's /koth/king marker contract."""

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


KING = Path(os.environ.get("KOTH_KING_PATH", "/koth/king"))
claim_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        request = urlsplit(self.path)
        status = 200

        if request.path == "/health":
            body = b"ok\n"
        elif request.path == "/claim":
            values = parse_qs(request.query, keep_blank_values=True).get("token", [])
            token = values[0].strip() if values else ""
            if not token or len(token) > 256 or "\n" in token or "\r" in token:
                status = 400
                body = b"invalid token\n"
            else:
                # Replace atomically so rsctf never reads a partially written token.
                with claim_lock:
                    temporary = KING.with_name(f".king-{os.getpid()}.tmp")
                    temporary.write_text(token, encoding="utf-8")
                    os.replace(temporary, KING)
                body = b"claim recorded\n"
        elif request.path == "/":
            body = b"rsctf KotH demo: submit your token at /claim?token=...\n"
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
