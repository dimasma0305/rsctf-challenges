"""Challenge-specific checks for the self-hosted A&D demo."""

import httpx

from lib import AdContext, Mumble, Offline, checker, run_ad_checker


REQUEST_TIMEOUT_SECONDS = 3
MAX_RESPONSE_BYTES = 4096


# This demo speaks HTTP. A raw TCP, binary, or custom TCP challenge can replace
# this function without changing lib.py or the decorated check shape.
def http_get(context: AdContext, path: str) -> str:
    host = f"[{context.target_ip}]" if ":" in context.target_ip else context.target_ip
    url = f"http://{host}:{context.target_port}{path}"
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=REQUEST_TIMEOUT_SECONDS,
            trust_env=False,
        ) as client:
            with client.stream(
                "GET",
                url,
                headers={"Accept-Encoding": "identity", "Connection": "close"},
            ) as response:
                if response.status_code != 200:
                    raise Mumble(f"the service returned HTTP {response.status_code}")
                body = bytearray()
                for chunk in response.iter_raw(chunk_size=1024):
                    if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise Mumble("the service response was too large")
                    body.extend(chunk)
    except Mumble:
        raise
    except (httpx.TimeoutException, httpx.NetworkError) as error:
        raise Offline("the service did not complete the request") from error
    except httpx.ProtocolError as error:
        raise Mumble("the service returned invalid HTTP") from error

    try:
        return body.decode("utf-8").rstrip("\r\n")
    except UnicodeDecodeError as error:
        raise Mumble("the service response was not UTF-8") from error


@checker
def check_health(context: AdContext) -> None:
    if http_get(context, "/health") != "ok":
        raise Mumble("the health endpoint did not return ok")


@checker
def check_flag(context: AdContext) -> None:
    if http_get(context, "/secret") != context.flag:
        raise Mumble("the secret endpoint did not return this round's flag")


if __name__ == "__main__":
    raise SystemExit(run_ad_checker())
