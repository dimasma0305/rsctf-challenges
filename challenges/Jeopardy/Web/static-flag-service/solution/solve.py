#!/usr/bin/env python3
"""Read the shared static flag from the public HTTP service."""

import argparse
import re
import urllib.request


FLAG = re.compile(r"rsctf\{[^{}\r\n]{1,256}\}")


def solve(url):
    """Request the service root and extract the static flag."""
    request = urllib.request.Request(f"{url.rstrip('/')}/", headers={"Connection": "close"})
    with urllib.request.urlopen(request, timeout=5) as response:
        text = response.read(1025).decode("utf-8")

    match = FLAG.search(text)
    if match is None:
        raise ValueError("service response did not contain an rsctf flag")
    return match.group(0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="issued shared-service URL")
    args = parser.parse_args()

    try:
        flag = solve(args.url)
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"solve failed: {error}\n")

    print(flag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
