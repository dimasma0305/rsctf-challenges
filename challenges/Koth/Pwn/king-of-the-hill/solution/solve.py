#!/usr/bin/env python3
"""Claim the marker-based hill with the team's current KotH token."""

import argparse
import urllib.parse
import urllib.request


def solve(url, token):
    """Submit the current token and return the service confirmation."""
    query = urllib.parse.urlencode({"token": token})
    request = urllib.request.Request(
        f"{url.rstrip('/')}/claim?{query}",
        headers={"Connection": "close"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        text = response.read(513).decode("utf-8").strip()

    if text != "claim recorded":
        raise ValueError("hill did not accept the claim")
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="issued hill URL")
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
