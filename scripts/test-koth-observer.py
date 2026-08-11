#!/usr/bin/env python3
"""Exercise the signed KotH arena referee against deterministic endpoints."""

import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parent.parent
OBSERVER_PATH = ROOT / "Koth/Web/api-observed-hill/observer/observer.py"
GAME_ID = 7
CHALLENGE_ID = 42
SECRET = "koth_api_" + ("a" * 64)
TOKEN = "koth_cycle_capability"
TOKEN_HASH = hashlib.sha256(TOKEN.encode()).hexdigest()
OTHER_VALID_HASH = hashlib.sha256(b"koth_other_current_capability").hexdigest()
UNKNOWN_HASH = hashlib.sha256(b"not-a-current-capability").hexdigest()
OBJECTIVE_IDS = ["proof-strength", "solve-speed"]


def objective_schema_hash() -> str:
    digest = hashlib.sha256()
    digest.update(len(OBJECTIVE_IDS).to_bytes(8, "big"))
    for objective_id in OBJECTIVE_IDS:
        encoded = objective_id.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def load_observer():
    spec = importlib.util.spec_from_file_location("rsctf_example_referee", OBSERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import the referee example")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Fixture:
    context = "1" * 64
    round_number = 3
    starts_at = 60_000
    ends_at = 180_001
    cycle_ends_at = 240_001
    now_ms = 65_000
    events: list[dict[str, object]] = []
    gap = False
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
        request = urlsplit(self.path)
        if request.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/hill/referee/evidence?after=0")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if request.path == f"/api/v1/koth/games/{GAME_ID}/challenges/{CHALLENGE_ID}/context":
            self._json(
                200,
                {
                    "apiVersion": "v1",
                    "context": Fixture.context,
                    "cycleNumber": 2,
                    "cycleEndsAt": Fixture.cycle_ends_at,
                    "resetAttempt": 0,
                    "roundNumber": Fixture.round_number,
                    "waveWindowStartsAt": Fixture.starts_at,
                    "waveWindowEndsAt": Fixture.ends_at,
                    "eligibleTokenHashes": [TOKEN_HASH, OTHER_VALID_HASH],
                    "objectiveIds": OBJECTIVE_IDS,
                    "objectiveSchemaHash": objective_schema_hash(),
                    "generatedAt": Fixture.starts_at + 1,
                },
            )
            return
        if request.path == "/hill/referee/evidence":
            Fixture.hill_headers.append(dict(self.headers.items()))
            query = parse_qs(request.query)
            after = int(query["after"][0])
            page = [event for event in Fixture.events if event["cursor"] > after]
            next_cursor = page[-1]["cursor"] if page else after
            latest = Fixture.events[-1]["cursor"] if Fixture.events else 0
            self._json(
                200,
                {
                    "activityTarget": 5,
                    "events": page,
                    "gap": Fixture.gap,
                    "hasMore": False,
                    "latestCursor": latest,
                    "nextCursor": next_cursor,
                },
            )
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
        decoded = json.loads(body)
        team_hashes = {
            team["tokenHash"]
            for wave in decoded["waves"]
            for team in wave["teams"]
        }
        Fixture.timestamps.append(int(timestamp))
        Fixture.observations.append(body)
        self._json(
            200,
            {
                "accepted": True,
                "cycleNumber": 2,
                "resetAttempt": 0,
                "roundNumber": Fixture.round_number,
                "submittedWaves": len(decoded["waves"]),
                "submittedTeams": len(team_hashes),
                "recognizedTeams": len(team_hashes),
                "acceptedAt": Fixture.starts_at + 2,
            },
        )

    def log_message(self, _format, *_args):
        pass


def evidence(
    cursor: int,
    token_hash: str,
    valid: bool,
    occurred_at: int | None = None,
) -> dict[str, object]:
    return {
        "cursor": cursor,
        "occurredAt": occurred_at or Fixture.starts_at + 1_000 + cursor,
        "tokenHash": token_hash,
        "valid": valid,
        "strength": {"earned": 4 if valid else 0, "possible": 5},
        "speed": {"earned": 50_000 if valid else 0, "possible": 60_000},
    }


def main() -> None:
    observer = load_observer()
    observer.time.time_ns = lambda: Fixture.now_ms * 1_000_000
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="rsctf-koth-referee-") as temporary:
            origin = f"http://127.0.0.1:{server.server_port}"
            state_file = Path(temporary) / "state.json"
            config = observer.Config(
                origin=origin,
                game_id=GAME_ID,
                challenge_id=CHALLENGE_ID,
                secret=SECRET,
                hill_url=f"{origin}/hill",
                poll_seconds=1,
                timeout_seconds=2,
                state_file=state_file,
            )
            client = observer.RefereeClient(config)

            if not client.poll_once():
                raise RuntimeError("the initial explicit-zero snapshot was not submitted")
            if client.poll_once():
                raise RuntimeError("unchanged arena evidence was reposted")

            Fixture.events = [
                evidence(1, TOKEN_HASH, False),
                evidence(2, TOKEN_HASH, True),
                evidence(3, UNKNOWN_HASH, True),
            ]
            Fixture.now_ms = 92_000
            if not client.poll_once():
                raise RuntimeError("the first finalized arena wave was not submitted")

            decoded = [json.loads(body) for body in Fixture.observations]
            expected_team = {
                "activity": {"earned": 1, "possible": 1},
                "isCrown": True,
                "objectives": [
                    {"earned": 4, "possible": 5},
                    {"earned": 50_000, "possible": 60_000},
                ],
                "tokenHash": TOKEN_HASH,
            }
            if decoded != [
                {
                    "context": "1" * 64,
                    "objectiveIds": OBJECTIVE_IDS,
                    "waves": [
                        {
                            "endedAtUnixMs": 60_000,
                            "teams": [],
                            "waveId": "proof-30000",
                        }
                    ],
                },
                {
                    "context": "1" * 64,
                    "objectiveIds": OBJECTIVE_IDS,
                    "waves": [
                        {
                            "endedAtUnixMs": 60_000,
                            "teams": [],
                            "waveId": "proof-30000",
                        },
                        {
                            "endedAtUnixMs": 90_000,
                            "teams": [expected_team],
                            "waveId": "proof-60000",
                        }
                    ],
                },
            ]:
                raise RuntimeError(f"unexpected arena snapshot bodies: {decoded!r}")
            if TOKEN.encode() in b"".join(Fixture.observations):
                raise RuntimeError("raw bearer capability leaked into signed evidence")
            if UNKNOWN_HASH in json.dumps(decoded):
                raise RuntimeError("unknown capability evidence was not filtered")

            restarted = observer.RefereeClient(config)
            if restarted.poll_once():
                raise RuntimeError("persisted referee state did not deduplicate a restart")
            if os.stat(state_file).st_mode & 0o077:
                raise RuntimeError("referee state file is accessible to another OS user")

            Fixture.events.extend(
                [
                    evidence(4, OTHER_VALID_HASH, True, 91_004),
                    evidence(5, TOKEN_HASH, True, 91_005),
                ]
            )
            Fixture.now_ms = 122_000
            if not restarted.poll_once():
                raise RuntimeError("the tied second wave was not submitted")
            tied_wave = json.loads(Fixture.observations[-1])["waves"][-1]
            tied_crowns = [
                team["tokenHash"] for team in tied_wave["teams"] if team["isCrown"]
            ]
            if tied_crowns:
                raise RuntimeError("an exact top-score tie incorrectly received a Crown")

            Fixture.events.append(evidence(6, OTHER_VALID_HASH, True, 121_006))
            Fixture.now_ms = 152_000
            if not restarted.poll_once():
                raise RuntimeError("the third finalized wave was not submitted")
            replacement_wave = json.loads(Fixture.observations[-1])["waves"][-1]
            replacement_crowns = [
                team["tokenHash"]
                for team in replacement_wave["teams"]
                if team["isCrown"]
            ]
            if replacement_crowns != [OTHER_VALID_HASH]:
                raise RuntimeError("the unique completed leader did not receive the Crown")

            # This wave crosses the RSCTF settlement boundary and is only
            # observed after the next context appears. Its end time assigns it
            # to that next window, so it must not disappear in a gap.
            Fixture.events.append(evidence(7, TOKEN_HASH, True, 179_000))
            Fixture.context = "2" * 64
            Fixture.round_number = 4
            Fixture.starts_at = 180_000
            Fixture.ends_at = 300_001
            Fixture.cycle_ends_at = 300_001
            Fixture.now_ms = 185_000
            if not restarted.poll_once():
                raise RuntimeError("a boundary-crossing wave was not settled")
            boundary = json.loads(Fixture.observations[-1])
            if (
                boundary["context"] != "2" * 64
                or [wave["waveId"] for wave in boundary["waves"]]
                != ["proof-150000"]
            ):
                raise RuntimeError("a boundary-crossing wave was lost or duplicated")

            Fixture.gap = True
            Fixture.events.append(evidence(8, TOKEN_HASH, True))
            try:
                restarted.poll_once()
            except RuntimeError as error:
                if "incomplete" not in str(error):
                    raise
            else:
                raise RuntimeError("a truncated evidence feed was scored")
            Fixture.gap = False

            if len(set(Fixture.timestamps)) != len(Fixture.timestamps):
                raise RuntimeError("referee timestamps were not unique")
            for headers in Fixture.hill_headers:
                if SECRET in json.dumps(headers):
                    raise RuntimeError("referee secret leaked to the arena request")

            redirect = observer.urllib.request.Request(f"{origin}/redirect")
            try:
                observer._request_json(redirect, 2)
            except observer.RefereeHttpError as error:
                if error.status != 302:
                    raise RuntimeError("referee returned the wrong redirect status") from error
            else:
                raise RuntimeError("referee followed an untrusted HTTP redirect")

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

    print(
        "OK: arena referee HMAC, normalization input, hash filtering, "
        "wave fencing, unique-leader Crowns, persistence, and fail-closed feed passed."
    )


if __name__ == "__main__":
    main()
