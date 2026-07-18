"""Challenge-specific checks for the platform-hosted A&D demo."""

import os
from time import monotonic

# The checker sandbox does not provide a terminal database. Set this before the
# convenience import so pwntools never attempts terminal initialization.
os.environ["PWNLIB_NOTERM"] = "1"

from pwn import context as pwn_context, remote
from pwnlib.exception import PwnlibException

from lib import AdContext, Mumble, Offline, checker, run_ad_checker


REQUEST_TIMEOUT_SECONDS = 3
MAX_RESPONSE_BYTES = 4096
pwn_context.log_level = "critical"


# This demo uses a tiny line protocol. Replace this function with the protocol
# your service speaks without changing lib.py or the decorated check shape.
def tcp_request(context: AdContext, command: str) -> str:
    if "\r" in command or "\n" in command:
        raise ValueError("checker commands must fit on one line")

    tube = None
    try:
        tube = remote(
            context.target_ip,
            context.target_port,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        tube.sendline(command.encode("ascii"))
        response = bytearray()
        deadline = monotonic() + REQUEST_TIMEOUT_SECONDS
        while b"\n" not in response and len(response) <= MAX_RESPONSE_BYTES:
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            try:
                chunk = tube.recv(
                    numb=min(1024, MAX_RESPONSE_BYTES + 1 - len(response)),
                    timeout=remaining,
                )
            except EOFError as error:
                if response:
                    break
                raise Offline("the service closed without a response") from error
            if chunk == b"":
                break
            response.extend(chunk)
    except Offline:
        raise
    except (EOFError, TimeoutError, PwnlibException, OSError) as error:
        raise Offline("the service did not complete the request") from error
    finally:
        if tube is not None:
            tube.close()

    if response == b"":
        raise Offline("the service timed out or closed without a response")
    if len(response) > MAX_RESPONSE_BYTES:
        raise Mumble("the service response was too large")

    line, newline, trailing = response.partition(b"\n")
    if newline == b"" or trailing != b"":
        raise Mumble("the service did not return a complete response line")
    try:
        return line.removesuffix(b"\r").decode("utf-8")
    except UnicodeDecodeError as error:
        raise Mumble("the service response was not UTF-8") from error


@checker
def check_ping(context: AdContext) -> None:
    if tcp_request(context, "PING") != "PONG":
        raise Mumble("PING did not return PONG")


@checker
def check_flag(context: AdContext) -> None:
    if tcp_request(context, "GET_FLAG") != context.flag:
        raise Mumble("GET_FLAG did not return this round's flag")


if __name__ == "__main__":
    raise SystemExit(run_ad_checker())
