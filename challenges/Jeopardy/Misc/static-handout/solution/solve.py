#!/usr/bin/env python3
"""Extract the flag from the shared text handout."""

import argparse
from pathlib import Path
import re


FLAG = re.compile(r"rsctf\{[^{}\r\n]{1,256}\}")


def solve(input_path):
    """Read the handout and return its first rsctf flag."""
    text = Path(input_path).read_text(encoding="utf-8")
    match = FLAG.search(text)
    if match is None:
        raise ValueError("handout does not contain an rsctf flag")
    return match.group(0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="path to welcome.txt")
    args = parser.parse_args()

    try:
        flag = solve(args.input)
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"solve failed: {error}\n")

    print(flag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
