"""API-native KotH arena with one-use proof-of-work objectives.

The player supplies a current RSCTF capability only when starting a puzzle.
The service hashes it immediately and retains only the SHA-256 digest. A
trusted external referee reads the bounded evidence feed and submits normalized
integer budgets to RSCTF; it never receives the bearer capability.
"""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
import hashlib
import json
import os
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


MAX_REQUEST_BYTES = 2_048
MAX_RESPONSE_EVENTS = 1_000
MAX_EVENTS = 50_000
MAX_SESSIONS = 10_000
MAX_RATE_KEYS = 4_096
MAX_COUNTER = 2_000_000
MAX_ATTEMPTS = 5
PUZZLE_DIFFICULTY = 4
PROOF_STRENGTH_TARGET = PUZZLE_DIFFICULTY + 1
PUZZLE_TTL_MS = 60_000
ACTIVITY_TARGET = 5
GLOBAL_STARTS_PER_SECOND = 100
TEAM_STARTS_PER_MINUTE = 20
TOKEN_PATTERN = re.compile(r"^koth_[A-Za-z0-9_-]{8,128}$")
BANNER = "rsctf API KotH arena: solve one-use puzzles; every team can score"


@dataclass
class Puzzle:
    token_hash: str
    nonce: str
    created_at_ms: int
    expires_at_ms: int
    attempts: int = 0
    closed: bool = False


state_lock = threading.Lock()
sessions: OrderedDict[str, Puzzle] = OrderedDict()
events: deque[dict[str, object]] = deque(maxlen=MAX_EVENTS)
next_cursor = 1
global_starts: deque[float] = deque()
team_starts: OrderedDict[str, deque[float]] = OrderedDict()


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def compact_json(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def prune_sessions(timestamp_ms: int) -> None:
    while sessions:
        session_id, session = next(iter(sessions.items()))
        if (
            len(sessions) <= MAX_SESSIONS
            and session.expires_at_ms + PUZZLE_TTL_MS >= timestamp_ms
        ):
            break
        sessions.pop(session_id, None)


def allow_start(client_ip: str, token_hash: str, timestamp: float) -> bool:
    while global_starts and global_starts[0] <= timestamp - 1:
        global_starts.popleft()
    if len(global_starts) >= GLOBAL_STARTS_PER_SECOND:
        return False

    key = hashlib.sha256(f"{client_ip}\0{token_hash}".encode()).hexdigest()
    bucket = team_starts.get(key)
    if bucket is None:
        if len(team_starts) >= MAX_RATE_KEYS:
            team_starts.popitem(last=False)
        bucket = deque()
        team_starts[key] = bucket
    else:
        team_starts.move_to_end(key)
    while bucket and bucket[0] <= timestamp - 60:
        bucket.popleft()
    if len(bucket) >= TEAM_STARTS_PER_MINUTE:
        return False
    global_starts.append(timestamp)
    bucket.append(timestamp)
    return True


def append_evidence(
    puzzle: Puzzle,
    *,
    valid: bool,
    proof_strength: int,
    timestamp_ms: int,
) -> None:
    global next_cursor

    elapsed_ms = min(PUZZLE_TTL_MS, max(0, timestamp_ms - puzzle.created_at_ms))
    events.append(
        {
            "cursor": next_cursor,
            "occurredAt": timestamp_ms,
            "tokenHash": puzzle.token_hash,
            "valid": valid,
            "strength": {
                "earned": min(proof_strength, PROOF_STRENGTH_TARGET)
                if valid
                else 0,
                "possible": PROOF_STRENGTH_TARGET,
            },
            "speed": {
                "earned": max(0, PUZZLE_TTL_MS - elapsed_ms) if valid else 0,
                "possible": PUZZLE_TTL_MS,
            },
        }
    )
    next_cursor += 1


class Handler(BaseHTTPRequestHandler):
    server_version = "rsctf-api-arena"
    sys_version = ""

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: object) -> None:
        self._send(status, compact_json(value), "application/json")

    def _text(self, status: int, text: str) -> None:
        self._send(status, text.encode(), "text/plain; charset=utf-8")

    def _read_json(self, expected_keys: set[str]) -> dict[str, object] | None:
        media_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
        if media_type.lower() != "application/json":
            self._json(415, {"error": "use application/json"})
            return None
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._json(413, {"error": "invalid request size"})
            return None
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"error": "invalid JSON"})
            return None
        if not isinstance(value, dict) or set(value) != expected_keys:
            self._json(400, {"error": "unexpected request fields"})
            return None
        return value

    def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        request = urlsplit(self.path)
        if request.path == "/health" and not request.query:
            self._text(200, "ok\n")
            return
        if request.path == "/" and not request.query:
            self._text(200, f"{BANNER}\n")
            return
        if request.path == "/referee/evidence":
            self._evidence(request.query)
            return
        self._text(404, "not found\n")

    def _evidence(self, query: str) -> None:
        try:
            values = parse_qs(query, strict_parsing=True)
            raw_after = values.get("after", [])
            if set(values) != {"after"} or len(raw_after) != 1:
                raise ValueError
            after = int(raw_after[0])
            if after < 0:
                raise ValueError
        except (TypeError, ValueError):
            self._json(400, {"error": "after must be one nonnegative integer"})
            return

        with state_lock:
            oldest = events[0]["cursor"] if events else next_cursor
            selected = [
                event for event in events if int(event["cursor"]) > after
            ][:MAX_RESPONSE_EVENTS]
            latest = next_cursor - 1
        next_value = int(selected[-1]["cursor"]) if selected else after
        self._json(
            200,
            {
                "activityTarget": ACTIVITY_TARGET,
                "events": selected,
                "gap": after + 1 < int(oldest),
                "hasMore": next_value < latest,
                "latestCursor": latest,
                "nextCursor": next_value,
            },
        )

    def do_POST(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        request = urlsplit(self.path)
        if request.query:
            self._json(400, {"error": "query parameters are not accepted"})
            return
        if request.path == "/start":
            self._start()
            return
        if request.path == "/solve":
            self._solve()
            return
        self._text(404, "not found\n")

    def _start(self) -> None:
        value = self._read_json({"token"})
        if value is None:
            return
        token = value["token"]
        if not isinstance(token, str) or not TOKEN_PATTERN.fullmatch(token):
            self._json(400, {"error": "invalid current KotH capability"})
            return
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        timestamp = time.monotonic()
        created_at = now_ms()
        with state_lock:
            allowed = allow_start(self.client_address[0], token_hash, timestamp)
            if allowed:
                prune_sessions(created_at)
                session_id = secrets.token_urlsafe(24)
                nonce = secrets.token_hex(16)
                puzzle = Puzzle(
                    token_hash=token_hash,
                    nonce=nonce,
                    created_at_ms=created_at,
                    expires_at_ms=created_at + PUZZLE_TTL_MS,
                )
                sessions[session_id] = puzzle
        if not allowed:
            self._json(429, {"error": "puzzle rate limit exceeded"})
            return
        # The raw token is no longer referenced after this method returns.
        self._json(
            201,
            {
                "algorithm": "sha256",
                "difficulty": PUZZLE_DIFFICULTY,
                "expiresAt": puzzle.expires_at_ms,
                "maxCounter": MAX_COUNTER,
                "nonce": nonce,
                "sessionId": session_id,
            },
        )

    def _solve(self) -> None:
        value = self._read_json({"sessionId", "counter"})
        if value is None:
            return
        session_id = value["sessionId"]
        counter = value["counter"]
        if (
            not isinstance(session_id, str)
            or not 16 <= len(session_id) <= 128
            or isinstance(counter, bool)
            or not isinstance(counter, int)
            or not 0 <= counter <= MAX_COUNTER
        ):
            self._json(400, {"error": "invalid solution"})
            return
        timestamp = now_ms()
        error: tuple[int, dict[str, str]] | None = None
        with state_lock:
            puzzle = sessions.get(session_id)
            if puzzle is None:
                error = (404, {"error": "unknown puzzle"})
            elif puzzle.closed:
                error = (409, {"error": "puzzle already closed"})
            elif timestamp >= puzzle.expires_at_ms:
                puzzle.closed = True
                error = (410, {"error": "puzzle expired"})
            else:
                nonce = puzzle.nonce
        if error is not None:
            self._json(*error)
            return

        candidate = hashlib.sha256(f"{nonce}:{counter}".encode()).hexdigest()
        proof_strength = len(candidate) - len(candidate.lstrip("0"))
        valid = proof_strength >= PUZZLE_DIFFICULTY
        race_lost = False
        with state_lock:
            puzzle = sessions.get(session_id)
            if puzzle is None or puzzle.closed:
                race_lost = True
            else:
                puzzle.attempts += 1
                puzzle.closed = valid or puzzle.attempts >= MAX_ATTEMPTS
                append_evidence(
                    puzzle,
                    valid=valid,
                    proof_strength=proof_strength,
                    timestamp_ms=timestamp,
                )
                remaining_attempts = max(0, MAX_ATTEMPTS - puzzle.attempts)
        if race_lost:
            self._json(409, {"error": "puzzle already closed"})
            return
        if valid:
            self._json(200, {"accepted": True, "digest": candidate})
        else:
            self._json(
                422,
                {
                    "accepted": False,
                    "remainingAttempts": remaining_attempts,
                },
            )

    def log_message(self, _format, *_args):
        # Suppress default access logging so player capability bodies cannot
        # appear in challenge logs.
        pass


port = int(os.environ.get("PORT", "8080"))
ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
