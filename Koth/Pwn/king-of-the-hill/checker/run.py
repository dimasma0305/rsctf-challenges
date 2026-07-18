"""Challenge-specific health check for the shared KotH demo."""

from http.client import HTTPConnection, HTTPException
import socket

from lib import KothContext, Mumble, Offline, checker, run_koth_checker


REQUEST_TIMEOUT_SECONDS = 3
MAX_RESPONSE_BYTES = 4096


# This demo speaks HTTP. A raw TCP, binary, or custom TCP challenge can replace
# this function without changing lib.py or the decorated check shape.
def http_get(context: KothContext, path: str) -> str:
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
        raise Offline("the service did not complete the request") from error
    except HTTPException as error:
        raise Mumble("the service returned invalid HTTP") from error
    finally:
        connection.close()

    if response.status != 200 or len(body) > MAX_RESPONSE_BYTES:
        raise Mumble("the service returned an unexpected HTTP response")
    try:
        return body.decode("utf-8").rstrip("\r\n")
    except UnicodeDecodeError as error:
        raise Mumble("the service response was not UTF-8") from error


@checker
def check_health(context: KothContext) -> None:
    if http_get(context, "/health") != "ok":
        raise Mumble("the health endpoint did not return ok")


@checker
def check_banner(context: KothContext) -> None:
    expected_banner = "rsctf KotH demo: submit your token at /claim?token=..."
    if http_get(context, "/") != expected_banner:
        raise Mumble("the public hill banner was incorrect")


if __name__ == "__main__":
    raise SystemExit(run_koth_checker())
