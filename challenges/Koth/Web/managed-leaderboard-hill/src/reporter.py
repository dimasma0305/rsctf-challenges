"""Lifecycle-bound in-target reporter for the RSCTF Leaderboard KotH example."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import hmac
import json
import math
import os
import threading
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request


MAX_RESPONSE_BYTES = 2 * 1_024 * 1_024
MAX_SUBMISSION_BYTES = 512 * 1_024
MAX_TEAMS = 2_000
MAX_WAVES = 64
MAX_PAGE_EVENTS = 1_000
WAVE_DURATION_MS = 30_000
WAVE_FINALIZATION_LAG_MS = 2_000
USER_AGENT = "rsctf-leaderboard-koth-example/4"
OBJECTIVE_IDS = ("proof-strength", "solve-speed")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


_DIRECT_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    _NoRedirect(),
)


class ReporterHttpError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status


@dataclass(frozen=True)
class Config:
    game_id: int
    challenge_id: int
    secret: str
    context_url: str
    observation_url: str
    poll_seconds: float
    timeout_seconds: float


@dataclass
class TeamTotals:
    completed_actions: int = 0
    attempts: int = 0
    strength_earned: int = 0
    strength_possible: int = 0
    speed_earned: int = 0
    speed_possible: int = 0
    first_completion_cursor: int | None = None


@dataclass(frozen=True)
class RoundContext:
    opaque: str
    cycle_number: int
    reset_attempt: int
    round_number: int
    starts_at: int
    ends_at: int
    cycle_ends_at: int
    eligible_hashes: frozenset[str]
    objective_ids: tuple[str, ...]
    objective_schema_hash: str | None


def _objective_schema_hash(objective_ids: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    digest.update(len(objective_ids).to_bytes(8, "big"))
    for objective_id in objective_ids:
        encoded = objective_id.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise ValueError(f"missing {name}")
    return value


def _positive_integer(name: str) -> int:
    try:
        value = int(_required_environment(name))
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _bounded_number(name: str, default: str, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name, default)
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be numeric") from error
    if not math.isfinite(value) or value < minimum or value > maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def _normalize_url(name: str, value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    try:
        parsed.port
    except ValueError as error:
        raise ValueError(f"{name} contains an invalid port") from error
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(ord(character) < 33 for character in value.strip())
    ):
        raise ValueError(
            f"{name} must be an absolute HTTP(S) URL "
            "without credentials, whitespace, or a query"
        )
    path = parsed.path.rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def load_config() -> Config | None:
    names = (
        "RSCTF_KOTH_GAME_ID",
        "RSCTF_KOTH_CHALLENGE_ID",
        "RSCTF_KOTH_CONTEXT_URL",
        "RSCTF_KOTH_OBSERVATION_URL",
        "RSCTF_KOTH_REPORTER_SECRET",
    )
    present = [bool(os.environ.get(name)) for name in names]
    if not any(present):
        return None
    if not all(present):
        missing = ", ".join(name for name in names if not os.environ.get(name))
        raise ValueError(f"incomplete managed reporter environment; missing {missing}")

    secret = _required_environment("RSCTF_KOTH_REPORTER_SECRET")
    if secret != secret.strip() or not secret.startswith("koth_target_") or len(secret) < 32:
        raise ValueError("RSCTF_KOTH_REPORTER_SECRET is not a valid target credential")
    return Config(
        game_id=_positive_integer("RSCTF_KOTH_GAME_ID"),
        challenge_id=_positive_integer("RSCTF_KOTH_CHALLENGE_ID"),
        secret=secret,
        context_url=_normalize_url(
            "RSCTF_KOTH_CONTEXT_URL",
            _required_environment("RSCTF_KOTH_CONTEXT_URL"),
        ),
        observation_url=_normalize_url(
            "RSCTF_KOTH_OBSERVATION_URL",
            _required_environment("RSCTF_KOTH_OBSERVATION_URL"),
        ),
        poll_seconds=_bounded_number("RSCTF_KOTH_POLL_SECONDS", "5", 1, 300),
        timeout_seconds=_bounded_number("RSCTF_KOTH_TIMEOUT_SECONDS", "5", 1, 60),
    )


def _request_json(request: urllib.request.Request, timeout: float) -> dict[str, Any]:
    try:
        with _DIRECT_OPENER.open(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        raw_detail = error.read(2_048).decode("utf-8", errors="replace").strip()
        detail = raw_detail.encode("unicode_escape").decode("ascii")[:512]
        raise ReporterHttpError(error.code, detail or "request rejected") from error
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError("remote JSON response exceeded the 2 MiB limit")
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("remote endpoint returned invalid JSON") from error
    if not isinstance(value, dict):
        raise RuntimeError("remote endpoint returned a non-object JSON value")
    return value


def _canonical_hash(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _integer(value: object, minimum: int, maximum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise RuntimeError(f"arena returned invalid {name}")
    return value


class ManagedReporter:
    def __init__(
        self,
        config: Config,
        read_evidence_page: Callable[[int], dict[str, Any]],
    ):
        self.config = config
        self.read_evidence_page = read_evidence_page
        self.context: RoundContext | None = None
        self.cursor = 0
        self.waves: dict[int, dict[str, TeamTotals]] = {}
        self.finalized_crowns: dict[int, str | None] = {}
        self.last_submitted_digest: str | None = None
        self.last_timestamp_ms = 0

    def _get_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )
        return _request_json(request, self.config.timeout_seconds)

    def fetch_context(self) -> RoundContext:
        value = self._get_json(self.config.context_url)
        expected = {
            "apiVersion",
            "context",
            "cycleNumber",
            "cycleEndsAt",
            "resetAttempt",
            "roundNumber",
            "waveWindowStartsAt",
            "waveWindowEndsAt",
            "eligibleTokenHashes",
            "objectiveIds",
            "objectiveSchemaHash",
            "generatedAt",
        }
        if set(value) != expected or value.get("apiVersion") != "v1":
            raise RuntimeError("RSCTF returned an unexpected KotH arena context")
        opaque = value["context"]
        hashes = value["eligibleTokenHashes"]
        objective_ids = value["objectiveIds"]
        objective_schema_hash = value["objectiveSchemaHash"]
        if (
            not _canonical_hash(opaque)
            or not isinstance(hashes, list)
            or not 1 <= len(hashes) <= MAX_TEAMS
            or any(not _canonical_hash(item) for item in hashes)
            or len(set(hashes)) != len(hashes)
        ):
            raise RuntimeError("RSCTF returned invalid eligible capability hashes")
        if objective_ids == []:
            if objective_schema_hash is not None:
                raise RuntimeError("RSCTF returned a hash without an objective schema")
        elif (
            objective_ids != list(OBJECTIVE_IDS)
            or not _canonical_hash(objective_schema_hash)
            or objective_schema_hash != _objective_schema_hash(OBJECTIVE_IDS)
        ):
            raise RuntimeError("RSCTF returned a different Leaderboard objective schema")
        starts_at = _integer(
            value["waveWindowStartsAt"], 0, 2**63 - 1, "waveWindowStartsAt"
        )
        ends_at = _integer(
            value["waveWindowEndsAt"],
            starts_at + 1,
            2**63 - 1,
            "waveWindowEndsAt",
        )
        cycle_ends_at = _integer(
            value["cycleEndsAt"],
            ends_at,
            2**63 - 1,
            "cycleEndsAt",
        )
        return RoundContext(
            opaque=opaque,
            cycle_number=_integer(value["cycleNumber"], 1, 2**31 - 1, "cycleNumber"),
            reset_attempt=_integer(value["resetAttempt"], 0, 2**31 - 1, "resetAttempt"),
            round_number=_integer(value["roundNumber"], 1, 2**31 - 1, "roundNumber"),
            starts_at=starts_at,
            ends_at=ends_at,
            cycle_ends_at=cycle_ends_at,
            eligible_hashes=frozenset(hashes),
            objective_ids=tuple(objective_ids),
            objective_schema_hash=objective_schema_hash,
        )

    def _fetch_page(self) -> dict[str, Any]:
        return self.read_evidence_page(self.cursor)

    def _consume_feed(self, context: RoundContext) -> bool:
        changed = False
        while True:
            value = self._fetch_page()
            expected = {
                "activityTarget",
                "events",
                "gap",
                "hasMore",
                "latestCursor",
                "nextCursor",
            }
            if set(value) != expected or value["gap"] is not False:
                raise RuntimeError("arena evidence feed is incomplete; refusing partial scoring")
            activity_target = _integer(value["activityTarget"], 1, 1_000_000, "activityTarget")
            if activity_target != 5:
                raise RuntimeError("arena changed its published activity target")
            page = value["events"]
            if not isinstance(page, list) or len(page) > MAX_PAGE_EVENTS:
                raise RuntimeError("arena returned an invalid evidence page")
            previous = self.cursor
            for event in page:
                if not isinstance(event, dict):
                    raise RuntimeError("arena returned a malformed evidence event")
                event_cursor = _integer(
                    event.get("cursor"),
                    1,
                    2**63 - 1,
                    "event cursor",
                )
                if event_cursor <= previous:
                    raise RuntimeError("arena evidence cursor did not advance")
                previous = event_cursor
                self._consume_event(event, context)
                changed = True
            next_value = _integer(value["nextCursor"], self.cursor, 2**63 - 1, "nextCursor")
            if page and next_value != previous:
                raise RuntimeError("arena evidence page cursor is inconsistent")
            if not page and next_value != self.cursor:
                raise RuntimeError("empty arena evidence page advanced its cursor")
            self.cursor = next_value
            if value["hasMore"] is False:
                return changed
            if value["hasMore"] is not True or not page:
                raise RuntimeError("arena evidence pagination did not make progress")

    def _consume_event(self, event: object, context: RoundContext) -> None:
        if not isinstance(event, dict) or set(event) != {
            "cursor",
            "occurredAt",
            "speed",
            "strength",
            "tokenHash",
            "valid",
        }:
            raise RuntimeError("arena returned a malformed evidence event")
        _integer(event["cursor"], 1, 2**63 - 1, "event cursor")
        occurred_at = _integer(event["occurredAt"], 0, 2**63 - 1, "event time")
        token_hash = event["tokenHash"]
        if not _canonical_hash(token_hash) or not isinstance(event["valid"], bool):
            raise RuntimeError("arena returned malformed evidence identity")
        ratios: list[tuple[int, int]] = []
        for name in ("strength", "speed"):
            ratio = event[name]
            if not isinstance(ratio, dict) or set(ratio) != {"earned", "possible"}:
                raise RuntimeError(f"arena returned malformed {name} evidence")
            possible = _integer(ratio["possible"], 1, 1_000_000_000_000, f"{name}.possible")
            earned = _integer(ratio["earned"], 0, possible, f"{name}.earned")
            ratios.append((earned, possible))
        if token_hash not in context.eligible_hashes:
            return
        wave_start = occurred_at // WAVE_DURATION_MS * WAVE_DURATION_MS
        wave_end = wave_start + WAVE_DURATION_MS
        if wave_end < context.starts_at or (
            context.round_number <= 1 and wave_end == context.starts_at
        ):
            # Ignore history before this event began. A wave may cross a later
            # settlement boundary: its server-confirmed end time assigns it to
            # exactly one contiguous RSCTF window.
            return
        if wave_start in self.finalized_crowns:
            raise RuntimeError("arena appended evidence to an already finalized wave")
        wave = self.waves.setdefault(wave_start, {})
        if token_hash not in wave and sum(len(teams) for teams in self.waves.values()) >= MAX_TEAMS:
            raise RuntimeError("arena evidence exceeded the 2,000 team-wave row bound")
        totals = wave.setdefault(token_hash, TeamTotals())
        totals.attempts += 1
        if event["valid"]:
            totals.completed_actions += 1
            if totals.first_completion_cursor is None:
                totals.first_completion_cursor = int(event["cursor"])
            totals.strength_earned += ratios[0][0]
            totals.strength_possible += ratios[0][1]
            totals.speed_earned += ratios[1][0]
            totals.speed_possible += ratios[1][1]

    @staticmethod
    def _performance(totals: TeamTotals) -> Fraction:
        return (
            Fraction(totals.strength_earned, totals.strength_possible)
            + Fraction(totals.speed_earned, totals.speed_possible)
        ) / 2

    def _finalize_wave(self, wave_start: int) -> None:
        completed = {
            token_hash: totals
            for token_hash, totals in self.waves.get(wave_start, {}).items()
            if totals.completed_actions > 0
        }
        if not completed:
            crown = None
        else:
            best = max(self._performance(totals) for totals in completed.values())
            tied = [
                token_hash
                for token_hash, totals in completed.items()
                if self._performance(totals) == best
            ]
            crown = tied[0] if len(tied) == 1 else None
        self.finalized_crowns[wave_start] = crown

    def _body(self, context: RoundContext, current_time_ms: int) -> bytes:
        cutoff = current_time_ms - WAVE_FINALIZATION_LAG_MS
        first_wave_end = (
            (context.starts_at + WAVE_DURATION_MS - 1) // WAVE_DURATION_MS
        ) * WAVE_DURATION_MS
        if context.round_number <= 1 and first_wave_end == context.starts_at:
            first_wave_end += WAVE_DURATION_MS
        finalized_starts = []
        wave_end = first_wave_end
        while wave_end < context.ends_at:
            if wave_end > cutoff:
                break
            wave_start = wave_end - WAVE_DURATION_MS
            finalized_starts.append(wave_start)
            wave_end += WAVE_DURATION_MS
        if len(finalized_starts) > MAX_WAVES:
            raise RuntimeError("settlement window contains more than 64 finalized arena waves")
        for wave_start in finalized_starts:
            if wave_start not in self.finalized_crowns:
                self._finalize_wave(wave_start)

        waves = []
        team_wave_rows = 0
        for wave_start in finalized_starts:
            crown = self.finalized_crowns[wave_start]
            teams = []
            for token_hash, totals in sorted(self.waves.get(wave_start, {}).items()):
                if totals.completed_actions == 0:
                    continue
                teams.append(
                    {
                        "activity": {"earned": 1, "possible": 1},
                        "isCrown": token_hash == crown,
                        "objectives": [
                            {
                                "earned": totals.strength_earned,
                                "possible": totals.strength_possible,
                            },
                            {
                                "earned": totals.speed_earned,
                                "possible": totals.speed_possible,
                            },
                        ],
                        "tokenHash": token_hash,
                    }
                )
            team_wave_rows += len(teams)
            waves.append(
                {
                    "endedAtUnixMs": wave_start + WAVE_DURATION_MS,
                    "teams": teams,
                    "waveId": f"proof-{wave_start}",
                }
            )
        if team_wave_rows > MAX_TEAMS:
            raise RuntimeError("snapshot exceeds RSCTF's 2,000 team-wave row bound")
        body = json.dumps(
            {
                "context": context.opaque,
                "objectiveIds": list(OBJECTIVE_IDS),
                "waves": waves,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        if len(body) > MAX_SUBMISSION_BYTES:
            raise RuntimeError("normalized Leaderboard snapshot exceeds RSCTF's 512 KiB limit")
        return body

    def _next_timestamp(self) -> str:
        current = time.time_ns() // 1_000_000
        self.last_timestamp_ms = max(current, self.last_timestamp_ms + 1)
        return str(self.last_timestamp_ms)

    def submit(self, context: RoundContext, body: bytes) -> dict[str, Any]:
        timestamp = self._next_timestamp()
        message = (
            f"{timestamp}.{self.config.game_id}.{self.config.challenge_id}.".encode()
            + body
        )
        signature = hmac.new(
            self.config.secret.encode(),
            message,
            hashlib.sha256,
        ).hexdigest()
        request = urllib.request.Request(
            self.config.observation_url,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
                "X-RSCTF-Timestamp": timestamp,
                "X-RSCTF-Signature": f"sha256={signature}",
            },
        )
        value = _request_json(request, self.config.timeout_seconds)
        decoded = json.loads(body)
        expected_waves = len(decoded["waves"])
        expected_teams = len(
            {
                team["tokenHash"]
                for wave in decoded["waves"]
                for team in wave["teams"]
            }
        )
        if (
            value.get("accepted") is not True
            or value.get("roundNumber") != context.round_number
            or value.get("submittedWaves") != expected_waves
            or value.get("submittedTeams") != expected_teams
            or value.get("recognizedTeams") != expected_teams
        ):
            raise RuntimeError("RSCTF did not acknowledge the complete arena snapshot")
        return value

    def poll_once(self) -> bool:
        context = self.fetch_context()
        if self.context is None or context.opaque != self.context.opaque:
            runtime_changed = self.context is not None and (
                context.cycle_number != self.context.cycle_number
                or context.reset_attempt != self.context.reset_attempt
            )
            if runtime_changed:
                # A managed target reset replaced the arena, so its local
                # evidence cursor restarted with the pristine container.
                self.cursor = 0
                self.waves = {}
                self.finalized_crowns = {}
            self.context = context
            # A normal RSCTF round change must retain any challenge wave that
            # crossed the settlement boundary. Older completed waves no longer
            # belong to a future request and can be discarded safely.
            self.waves = {
                start: rows
                for start, rows in self.waves.items()
                if start + WAVE_DURATION_MS >= context.starts_at
            }
            self.finalized_crowns = {
                start: crown
                for start, crown in self.finalized_crowns.items()
                if start + WAVE_DURATION_MS >= context.starts_at
            }
            self.last_submitted_digest = None
        else:
            # Hash membership is part of the context contract even though the
            # opaque fence already changes with each issuance window.
            self.context = context
        self._consume_feed(context)
        body = self._body(context, time.time_ns() // 1_000_000)
        digest = hashlib.sha256(body).hexdigest()
        if digest == self.last_submitted_digest:
            return False
        accepted = self.submit(context, body)
        self.last_submitted_digest = digest
        print(
            "accepted KotH Leaderboard snapshot:"
            f" round={accepted.get('roundNumber')}"
            f" waves={accepted.get('submittedWaves')}"
            f" teams={accepted.get('recognizedTeams')}"
            f" cycle={accepted.get('cycleNumber')}"
            f" reset={accepted.get('resetAttempt')}",
            flush=True,
        )
        return True


def _retry_delay(failures: int, poll_seconds: float) -> float:
    return min(30.0, max(1.0, poll_seconds) * (2 ** min(failures - 1, 5)))


def start_managed_reporter(
    read_evidence_page: Callable[[int], dict[str, Any]],
) -> threading.Thread | None:
    """Start reporting when rsctf injected the complete managed-target contract."""
    try:
        config = load_config()
    except ValueError as error:
        print(f"managed reporter configuration error: {error}", flush=True)
        return None
    if config is None:
        print("managed reporter disabled: rsctf environment is absent", flush=True)
        return None

    client = ManagedReporter(config, read_evidence_page)

    def run() -> None:
        failures = 0
        while True:
            try:
                client.poll_once()
                failures = 0
                time.sleep(config.poll_seconds)
            except (ReporterHttpError, urllib.error.URLError, OSError, RuntimeError) as error:
                failures += 1
                print(f"managed reporter error: {error}", flush=True)
                time.sleep(_retry_delay(failures, config.poll_seconds))

    thread = threading.Thread(target=run, name="rsctf-koth-reporter", daemon=True)
    thread.start()
    return thread
