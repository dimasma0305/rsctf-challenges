#!/usr/bin/env python3
"""Trusted bridge from the demo hill's control state to RSCTF's signed API."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import os
import sys
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


MAX_RESPONSE_BYTES = 16 * 1024
MAX_TOKEN_BYTES = 256
USER_AGENT = "rsctf-api-koth-example/1"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


_DIRECT_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    _NoRedirect(),
)


class ObserverHttpError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status


@dataclass(frozen=True)
class Config:
    origin: str
    game_id: int
    challenge_id: int
    secret: str
    hill_url: str
    poll_seconds: float
    timeout_seconds: float

    @property
    def api_base(self) -> str:
        return (
            f"{self.origin}/api/v1/koth/games/{self.game_id}"
            f"/challenges/{self.challenge_id}"
        )


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


def _normalize_url(name: str, value: str, allow_http: bool) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    try:
        parsed.port
    except ValueError as error:
        raise ValueError(f"{name} contains an invalid port") from error
    allowed_schemes = {"https"}
    if allow_http:
        allowed_schemes.add("http")
    if (
        parsed.scheme not in allowed_schemes
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(ord(character) < 33 for character in value.strip())
    ):
        expected = "https" if not allow_http else "http or https"
        raise ValueError(
            f"{name} must be an absolute {expected} URL "
            "without credentials, whitespace, or a query"
        )
    path = parsed.path.rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def load_config(allow_http: bool) -> Config:
    secret = _required_environment("RSCTF_KOTH_OBSERVER_SECRET")
    if (
        secret != secret.strip()
        or not secret.startswith("koth_api_")
        or len(secret) < 32
    ):
        raise ValueError("RSCTF_KOTH_OBSERVER_SECRET is not a valid copied observer secret")
    return Config(
        origin=_normalize_url(
            "RSCTF_ORIGIN",
            _required_environment("RSCTF_ORIGIN"),
            allow_http,
        ),
        game_id=_positive_integer("RSCTF_GAME_ID"),
        challenge_id=_positive_integer("RSCTF_CHALLENGE_ID"),
        secret=secret,
        hill_url=_normalize_url(
            "RSCTF_KOTH_HILL_URL",
            _required_environment("RSCTF_KOTH_HILL_URL"),
            allow_http,
        ),
        poll_seconds=_bounded_number("RSCTF_KOTH_POLL_SECONDS", "5", 1, 300),
        timeout_seconds=_bounded_number("RSCTF_KOTH_TIMEOUT_SECONDS", "5", 1, 60),
    )


def _request_json(request: urllib.request.Request, timeout: float) -> dict[str, Any]:
    try:
        with _DIRECT_OPENER.open(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        raw_detail = error.read(2048).decode("utf-8", errors="replace").strip()
        detail = raw_detail.encode("unicode_escape").decode("ascii")[:512]
        raise ObserverHttpError(error.code, detail or "request rejected") from error
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError("remote JSON response exceeded the 16 KiB limit")
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("remote endpoint returned invalid JSON") from error
    if not isinstance(value, dict):
        raise RuntimeError("remote endpoint returned a non-object JSON value")
    return value


def _valid_context(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


class ObserverClient:
    def __init__(self, config: Config):
        self.config = config
        self.last_state: tuple[str, str | None] | None = None
        self.last_timestamp_ms = 0

    def _get_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        return _request_json(request, self.config.timeout_seconds)

    def fetch_context(self) -> str:
        value = self._get_json(f"{self.config.api_base}/context")
        context = value.get("context")
        if value.get("apiVersion") != "v1" or not _valid_context(context):
            raise RuntimeError("RSCTF returned an invalid KotH observer context")
        return context

    def fetch_token(self) -> str | None:
        value = self._get_json(f"{self.config.hill_url}/control")
        if set(value) != {"token"}:
            raise RuntimeError("hill /control must return exactly one token property")
        token = value["token"]
        if token is None:
            return None
        if (
            not isinstance(token, str)
            or token == ""
            or len(token.encode("utf-8")) > MAX_TOKEN_BYTES
        ):
            raise RuntimeError("hill returned an invalid controller capability")
        return token

    def _next_timestamp(self) -> str:
        now_ms = time.time_ns() // 1_000_000
        self.last_timestamp_ms = max(now_ms, self.last_timestamp_ms + 1)
        return str(self.last_timestamp_ms)

    def submit(self, context: str, token: str | None) -> dict[str, Any]:
        body = json.dumps(
            {"context": context, "token": token},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
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
            f"{self.config.api_base}/observations",
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
        if value.get("accepted") is not True:
            raise RuntimeError("RSCTF did not acknowledge the observation")
        return value

    def poll_once(self) -> bool:
        context = self.fetch_context()
        token = self.fetch_token()
        state = (context, token)
        if state == self.last_state:
            return False
        accepted = self.submit(context, token)
        self.last_state = state
        controller = "uncaptured" if token is None else "capability present"
        print(
            "accepted KotH observation:"
            f" cycle={accepted.get('cycleNumber')}"
            f" reset={accepted.get('resetAttempt')}"
            f" state={controller}",
            flush=True,
        )
        return True


def _retry_delay(failures: int, poll_seconds: float) -> float:
    return min(30.0, max(1.0, poll_seconds) * (2 ** min(failures - 1, 5)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="submit one changed observation and exit (installation preflight)",
    )
    parser.add_argument(
        "--allow-insecure-http",
        action="store_true",
        help="allow http:// URLs for local testing only",
    )
    arguments = parser.parse_args(argv)
    try:
        config = load_config(arguments.allow_insecure_http)
    except ValueError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2

    client = ObserverClient(config)
    failures = 0
    while True:
        try:
            client.poll_once()
            failures = 0
            if arguments.once:
                return 0
            time.sleep(config.poll_seconds)
        except (ObserverHttpError, urllib.error.URLError, OSError, RuntimeError) as error:
            failures += 1
            print(f"observer error: {error}", file=sys.stderr, flush=True)
            if arguments.once:
                return 1
            time.sleep(_retry_delay(failures, config.poll_seconds))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
