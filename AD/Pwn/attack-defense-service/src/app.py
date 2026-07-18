"""Intentionally vulnerable A&D demo service.

The checker plants the current flag through /plant; attackers read it at /flag.
This is deliberately trivial so operators can verify the complete A&D path.
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


flag_lock = threading.Lock()
current_flag = os.environ.get("RSCTF_FLAG", "flag-not-planted-yet")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        global current_flag

        request = urlsplit(self.path)
        status = 200
        if request.path == "/health":
            body = b"ok\n"
        elif request.path == "/flag":
            with flag_lock:
                body = (current_flag + "\n").encode()
        elif request.path == "/plant":
            values = parse_qs(request.query, keep_blank_values=True).get("flag", [])
            candidate = values[0] if values else ""
            if not candidate or len(candidate) > 256 or "\n" in candidate or "\r" in candidate:
                status = 400
                body = b"invalid flag\n"
            else:
                with flag_lock:
                    current_flag = candidate
                body = b"ok\n"
        elif request.path == "/":
            body = b"rsctf A&D demo: inspect /flag\n"
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
