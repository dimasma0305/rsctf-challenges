"""rsctf A&D checker for the self-hosted /secret demo service."""

from dataclasses import dataclass
from enum import IntEnum
from http.client import HTTPConnection, HTTPException
from ipaddress import ip_address
import os
import socket


REQUEST_TIMEOUT_SECONDS = 3
MAX_RESPONSE_BYTES = 4096


class Verdict(IntEnum):
    OK = 0
    MUMBLE = 1
    OFFLINE = 2
    INTERNAL_ERROR = 3


class Mumble(Exception):
    """The target answered, but its behavior was incorrect."""


class Offline(Exception):
    """The target could not provide a complete response."""


@dataclass(frozen=True)
class Context:
    target_ip: str
    target_port: int
    round_number: int
    participation_id: int  # RSCTF_TEAM_ID currently contains participation ID.
    challenge_id: int
    flag: str


def required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise ValueError(f"missing {name}")
    return value


def positive_integer(name: str, maximum: int | None = None) -> int:
    value = int(required(name))
    if value <= 0 or (maximum is not None and value > maximum):
        raise ValueError(f"invalid {name}")
    return value


def load_context() -> Context:
    if required("RSCTF_ACTION").strip() != "check":
        raise ValueError("unsupported RSCTF_ACTION")
    return Context(
        target_ip=str(ip_address(required("RSCTF_TARGET_IP").strip())),
        target_port=positive_integer("RSCTF_TARGET_PORT", 65535),
        round_number=positive_integer("RSCTF_ROUND"),
        participation_id=positive_integer("RSCTF_TEAM_ID"),
        challenge_id=positive_integer("RSCTF_CHALLENGE_ID"),
        flag=required("RSCTF_FLAG"),
    )


def get_text(context: Context, path: str) -> str:
    connection = HTTPConnection(
        context.target_ip,
        context.target_port,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    try:
        connection.request("GET", path, headers={"Connection": "close"})
        response = connection.getresponse()
        body = response.read(MAX_RESPONSE_BYTES + 1)
    except (TimeoutError, socket.timeout, ConnectionError, OSError) as error:
        raise Offline from error
    except HTTPException as error:
        raise Mumble from error
    finally:
        connection.close()

    if response.status != 200 or len(body) > MAX_RESPONSE_BYTES:
        raise Mumble
    try:
        return body.decode("utf-8").rstrip("\r\n")
    except UnicodeDecodeError as error:
        raise Mumble from error


def check(context: Context) -> None:
    if get_text(context, "/health") != "ok":
        raise Mumble
    if get_text(context, "/secret") != context.flag:
        raise Mumble


def main() -> int:
    try:
        context = load_context()
    except Exception:
        return Verdict.INTERNAL_ERROR
    try:
        check(context)
    except Offline:
        return Verdict.OFFLINE
    except Mumble:
        return Verdict.MUMBLE
    except Exception:
        return Verdict.INTERNAL_ERROR
    return Verdict.OK


if __name__ == "__main__":
    raise SystemExit(main())
