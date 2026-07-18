"""Intentionally vulnerable raw-TCP platform-hosted A&D demo service.

rsctf writes the rotating flag to RSCTF_FLAG_FILE before each checker pass.
This service reads the file for every GET_FLAG command, so it never caches an
old round.
"""

import os
from pathlib import Path
import socketserver


FLAG_FILE = Path(os.environ.get("RSCTF_FLAG_FILE", "/run/rsctf/flag"))


def read_current_flag() -> str:
    """Read the current round instead of caching the creation-time environment."""
    try:
        return FLAG_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "flag-not-delivered-yet"


class Handler(socketserver.StreamRequestHandler):
    """Handle one bounded, newline-framed command per connection."""

    def handle(self) -> None:
        request = self.rfile.readline(65)
        if request == b"":
            return
        if len(request) > 64 or not request.endswith(b"\n"):
            self.wfile.write(b"ERR malformed command\n")
            return

        try:
            command = request.decode("ascii").rstrip("\r\n")
        except UnicodeDecodeError:
            self.wfile.write(b"ERR malformed command\n")
            return

        if command == "PING":
            response = b"PONG\n"
        elif command == "GET_FLAG":
            response = (read_current_flag() + "\n").encode()
        else:
            response = b"ERR unknown command\n"
        self.wfile.write(response)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


port = int(os.environ.get("PORT", "8080"))
with Server(("0.0.0.0", port), Handler) as server:
    server.serve_forever()
