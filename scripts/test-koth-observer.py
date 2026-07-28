#!/usr/bin/env python3
"""Exercise the signed KotH observer against deterministic local endpoints."""

import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = Path(__file__).resolve().parent.parent
OBSERVER_PATH = ROOT / "Koth/Web/api-observed-hill/observer/observer.py"
GAME_ID = 7
CHALLENGE_ID = 42
SECRET = "koth_api_" + ("a" * 64)


def load_observer():
    spec = importlib.util.spec_from_file_location("rsctf_example_observer", OBSERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import the observer example")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Fixture:
    context = "1" * 64
    token = "koth_cycle_capability"
    observations: list[bytes] = []
    timestamps: list[int] = []
    hill_headers: list[dict[str, str]] = []


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, value: object) -> None:
        body = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/hill/control")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == f"/api/v1/koth/games/{GAME_ID}/challenges/{CHALLENGE_ID}/context":
            self._json(
                200,
                {
                    "apiVersion": "v1",
                    "context": Fixture.context,
                    "cycleNumber": 3,
                    "resetAttempt": 0,
                    "generatedAt": 1,
                },
            )
            return
        if self.path == "/hill/control":
            Fixture.hill_headers.append(dict(self.headers.items()))
            self._json(200, {"token": Fixture.token})
            return
        self._json(404, {"title": "not found", "status": 404})

    def do_POST(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path != (
            f"/api/v1/koth/games/{GAME_ID}/challenges/"
            f"{CHALLENGE_ID}/observations"
        ):
            self._json(404, {"title": "not found", "status": 404})
            return
        body = self.rfile.read(int(self.headers["Content-Length"]))
        timestamp = self.headers["X-RSCTF-Timestamp"]
        message = f"{timestamp}.{GAME_ID}.{CHALLENGE_ID}.".encode() + body
        expected = "sha256=" + hmac.new(
            SECRET.encode(),
            message,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(self.headers["X-RSCTF-Signature"], expected):
            self._json(401, {"title": "unauthorized", "status": 401})
            return
        if Fixture.timestamps and int(timestamp) <= Fixture.timestamps[-1]:
            self._json(409, {"title": "out of order", "status": 409})
            return
        Fixture.timestamps.append(int(timestamp))
        Fixture.observations.append(body)
        self._json(
            200,
            {
                "accepted": True,
                "cycleNumber": 3,
                "resetAttempt": 0,
                "acceptedAt": 1,
            },
        )

    def log_message(self, _format, *_args):
        pass


def main() -> None:
    observer = load_observer()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        origin = f"http://127.0.0.1:{server.server_port}"
        config = observer.Config(
            origin=origin,
            game_id=GAME_ID,
            challenge_id=CHALLENGE_ID,
            secret=SECRET,
            hill_url=f"{origin}/hill",
            poll_seconds=1,
            timeout_seconds=2,
        )
        client = observer.ObserverClient(config)

        if not client.poll_once():
            raise RuntimeError("the first controller observation was not submitted")
        if client.poll_once():
            raise RuntimeError("unchanged context and capability were reposted")

        Fixture.context = "2" * 64
        if not client.poll_once():
            raise RuntimeError("a changed RSCTF context was not submitted")

        Fixture.token = None
        if not client.poll_once():
            raise RuntimeError("an explicit uncaptured state was not submitted")

        decoded = [json.loads(body) for body in Fixture.observations]
        expected = [
            {"context": "1" * 64, "token": "koth_cycle_capability"},
            {"context": "2" * 64, "token": "koth_cycle_capability"},
            {"context": "2" * 64, "token": None},
        ]
        if decoded != expected:
            raise RuntimeError(f"unexpected observation bodies: {decoded!r}")
        if len(set(Fixture.timestamps)) != len(Fixture.timestamps):
            raise RuntimeError("observer timestamps were not unique")
        for headers in Fixture.hill_headers:
            if SECRET in json.dumps(headers):
                raise RuntimeError("observer secret leaked to the hill request")

        redirect = observer.urllib.request.Request(f"{origin}/redirect")
        try:
            observer._request_json(redirect, 2)
        except observer.ObserverHttpError as error:
            if error.status != 302:
                raise RuntimeError("observer returned the wrong redirect status") from error
        else:
            raise RuntimeError("observer followed an untrusted HTTP redirect")

        try:
            observer._normalize_url("test", "http://example.test", False)
        except ValueError:
            pass
        else:
            raise RuntimeError("insecure HTTP was accepted without explicit opt-in")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    print("OK: signed KotH observer HMAC, context fencing, null state, and dedup passed.")


if __name__ == "__main__":
    main()
