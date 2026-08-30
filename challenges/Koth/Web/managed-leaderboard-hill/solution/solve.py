#!/usr/bin/env python3
"""Solve one managed proof-arena puzzle with the team's current KotH token."""

import argparse
import hashlib
import json
import urllib.request


def post_json(url, path, value):
    """POST one bounded JSON request and return its object response."""
    data = json.dumps(value, separators=(",", ":")).encode()
    request = urllib.request.Request(
        f"{url.rstrip('/')}{path}",
        data=data,
        headers={"Content-Type": "application/json", "Connection": "close"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.loads(response.read(4097))
    if not isinstance(result, dict):
        raise ValueError("service returned a non-object JSON response")
    return result


def solve(url, token):
    """Start a puzzle, find a valid counter, and submit it once."""
    puzzle = post_json(url, "/start", {"token": token})
    nonce = puzzle.get("nonce")
    session_id = puzzle.get("sessionId")
    difficulty = puzzle.get("difficulty")
    maximum = puzzle.get("maxCounter")
    if (
        not isinstance(nonce, str)
        or not isinstance(session_id, str)
        or not isinstance(difficulty, int)
        or not 1 <= difficulty <= 8
        or not isinstance(maximum, int)
        or not 0 <= maximum <= 2_000_000
    ):
        raise ValueError("service returned an invalid puzzle")

    prefix = "0" * difficulty
    for counter in range(maximum + 1):
        digest = hashlib.sha256(f"{nonce}:{counter}".encode()).hexdigest()
        if digest.startswith(prefix):
            break
    else:
        raise ValueError("no valid counter exists inside the advertised range")

    result = post_json(url, "/solve", {"sessionId": session_id, "counter": counter})
    if result.get("accepted") is not True or result.get("digest") != digest:
        raise ValueError("service rejected the proof")
    return f"accepted counter={counter} digest={digest}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="issued proof-arena URL")
    parser.add_argument("--token", required=True, help="current team KotH token")
    args = parser.parse_args()

    try:
        result = solve(args.url, args.token)
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"solve failed: {error}\n")

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
