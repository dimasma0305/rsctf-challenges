#!/usr/bin/env python3
"""Solve the generated team-sum variant."""

import argparse


def solve(left, right):
    """Return the flag derived from the two player-visible integers."""
    return f"rsctf{{sum_{left + right}}}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=int, help="first generated integer")
    parser.add_argument("right", type=int, help="second generated integer")
    args = parser.parse_args()
    print(solve(args.left, args.right))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
