#!/usr/bin/env python3
"""Explain why the current DynamicAttachment example cannot be solved."""

import argparse
from pathlib import Path


def solve(input_path):
    """Inspect the illustrative bundle and report the missing assignment step."""
    Path(input_path).read_bytes()
    raise ValueError(
        "schema-only example: rsctf does not assign a per-participation handout and flag"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="path to the illustrative bundle")
    args = parser.parse_args()

    try:
        print(solve(args.input))
    except (OSError, ValueError) as error:
        parser.exit(2, f"not playable: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
