"""A&D rehearsal service with a health check and a rotating round proof."""

import hmac
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


FLAG_FILE = Path(os.environ.get("RSCTF_FLAG_FILE", "/flag"))
BANNER = Path(__file__).with_name("banner.txt")
FLAG = re.compile(rb"flag\{[A-Za-z0-9_-]{32}\}")
PROOF_PATH = re.compile(r"/proof/([a-f0-9]{32})")


def read_small_file(path):
    try:
        with path.open("rb") as file:
            return file.read(129).strip()
    except OSError:
        return b""


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(2)

    def do_GET(self):
        if self.path == "/healthz":
            self.reply(200, b"ok")
            return
        if self.path == "/":
            banner = read_small_file(BANNER)
            self.reply(200 if 0 < len(banner) <= 128 else 503, banner[:128])
            return

        match = PROOF_PATH.fullmatch(self.path)
        if not match:
            self.reply(404, b"not found")
            return
        flag = read_small_file(FLAG_FILE)
        if not FLAG.fullmatch(flag):
            self.reply(503, b"round flag unavailable")
            return
        nonce = bytes.fromhex(match[1])
        self.reply(200, hmac.digest(flag, nonce, "sha256").hex().encode("ascii"))

    def reply(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    with ThreadingHTTPServer(("0.0.0.0", 8080), Handler) as server:
        server.serve_forever()
