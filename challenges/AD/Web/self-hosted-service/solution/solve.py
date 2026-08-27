#!/usr/bin/env python3
"""Retrieve the current BYOC A&D flag from the public HTTP service."""

import argparse
import re
import urllib.request


FLAG = re.compile(r"rsctf\{[^{}\r\n]{1,256}\}")


def solve(url):
    """Request the intentionally exposed secret endpoint."""
    request = urllib.request.Request(
        f"{url.rstrip('/')}/secret",
        headers={"Connection": "close"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        text = response.read(513).decode("utf-8").strip()

    if not FLAG.fullmatch(text):
        raise ValueError("service did not return an rsctf flag")
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="issued service URL")
    args = parser.parse_args()

    try:
        flag = solve(args.url)
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"solve failed: {error}\n")

    print(flag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
