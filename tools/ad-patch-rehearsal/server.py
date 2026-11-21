"""Serve one rehearsal exercise and prove receipt of the current round flag."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re

from exercise import evaluate


class Handler(BaseHTTPRequestHandler):
    timeout = 2

    def reply(self, status, body):
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self.reply(200, b"ok")
        match = re.fullmatch(r"/round/([0-9a-f]{32})", self.path)
        if match is None:
            return self.reply(404, b"")
        try:
            with Path(os.getenv("RSCTF_FLAG_FILE", "/flag")).open("rb") as source:
                flag = source.read(128).strip()
        except OSError:
            flag = b""
        if not flag:
            return self.reply(503, b"")
        proof = hmac.new(flag, match[1].encode("ascii"), hashlib.sha256).hexdigest()
        self.reply(200, proof.encode("ascii"))

    def do_POST(self):
        if self.path != "/evaluate":
            return self.reply(404, b"")
        try:
            size = int(self.headers.get("Content-Length", "-1"))
            if not 0 < size <= 1024:
                return self.reply(400, b"")
            value = json.loads(self.rfile.read(size))
            result = json.dumps(evaluate(value)).encode()
        except (AttributeError, TypeError, ValueError, RecursionError):
            return self.reply(400, b"")
        self.reply(200, result)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    with HTTPServer((os.getenv("BIND", "0.0.0.0"), int(os.getenv("PORT", "8080"))), Handler) as server:
        print(server.server_port, flush=True)
        server.serve_forever()
