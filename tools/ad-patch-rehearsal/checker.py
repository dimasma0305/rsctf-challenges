"""Check normal service behavior and a fresh proof for the engine's current flag."""
import hashlib
import hmac
from http.client import HTTPConnection, HTTPException
import json
import secrets

from lib import Mumble, Offline, checker, run_ad_checker
from case_data import INPUT, EXPECTED


def request(ctx, method, path, body=None):
    connection = HTTPConnection(ctx.target_ip, ctx.target_port, timeout=2)
    try:
        connection.request(method, path, body)
        response = connection.getresponse()
        result = response.read(1025)
    except (OSError, HTTPException) as error:
        raise Offline("service did not complete its response") from error
    finally:
        connection.close()
    if response.status != 200 or len(result) > 1024:
        raise Mumble("unexpected service response")
    return result


@checker
def functionality(ctx):
    result = request(ctx, "POST", "/evaluate", json.dumps(INPUT))
    try:
        correct = json.loads(result) == EXPECTED
    except (ValueError, RecursionError):
        correct = False
    if not correct:
        raise Mumble("exercise returned the wrong result")


@checker
def current_round(ctx):
    nonce = secrets.token_hex(16)
    expected = hmac.new(ctx.flag.encode(), nonce.encode(), hashlib.sha256).hexdigest().encode()
    if not hmac.compare_digest(request(ctx, "GET", f"/round/{nonce}"), expected):
        raise Mumble("current round proof did not match")


if __name__ == "__main__":
    raise SystemExit(run_ad_checker())
