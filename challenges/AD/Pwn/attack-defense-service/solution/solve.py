#!/usr/bin/env python3
"""Retrieve the current A&D flag through the public line protocol."""

import argparse
import re
import socket


FLAG = re.compile(r"flag\{[A-Za-z0-9_-]{32}\}")


def solve(host, port):
    """Send GET_FLAG and return the current round flag."""
    with socket.create_connection((host, port), timeout=5) as connection:
        connection.sendall(b"GET_FLAG\n")
        with connection.makefile("rb") as stream:
            response = stream.readline(513)

    text = response.decode("utf-8").strip()
    if len(response) > 512 or not FLAG.fullmatch(text):
        raise ValueError("service did not return a canonical A&D flag")
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    try:
        flag = solve(args.host, args.port)
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"solve failed: {error}\n")

    print(flag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
