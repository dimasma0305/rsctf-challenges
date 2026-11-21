"""Serve one rehearsal exercise and prove receipt of the current round flag."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import sqlite3

from exercise import evaluate


def load_installation_id():
    # Each service owns one row on its data volume. Overlapping revisions
    # opening that volume must agree on the first committed identifier.
    directory = Path(os.getenv("REHEARSAL_DATA_DIR", "/var/lib/rehearsal"))
    db = sqlite3.connect(directory / "state.sqlite")
    try:
        with db:
            db.execute("CREATE TABLE IF NOT EXISTS installation (id INTEGER PRIMARY KEY, marker TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO installation VALUES (1, lower(hex(randomblob(16))))")
            return db.execute("SELECT marker FROM installation WHERE id=1").fetchone()[0].encode("ascii")
    finally:
        db.close()


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
        if self.path == "/installation":
            return self.reply(200, self.server.installation_id)
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
        server.installation_id = load_installation_id()
        print(server.server_port, flush=True)
        server.serve_forever()
