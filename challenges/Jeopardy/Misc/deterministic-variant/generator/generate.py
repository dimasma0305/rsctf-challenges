#!/usr/bin/env python3
"""Deterministic rsctf per-participation variant generator example."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from typing import Any


INPUT_ENV = "RSCTF_VARIANT_INPUT"
DOMAIN = b"rsctf-example-sum-variant-v1\0"


def decode_input(encoded: str) -> dict[str, Any]:
    if not encoded or len(encoded) > 4096:
        raise ValueError(f"{INPUT_ENV} is missing or too large")
    padding = "=" * (-len(encoded) % 4)
    try:
        raw = base64.urlsafe_b64decode(encoded + padding)
        value = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"{INPUT_ENV} is not valid URL-safe base64 JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{INPUT_ENV} must decode to an object")
    required = {"gameId", "challengeId", "participationId", "revision", "seed"}
    if set(value) != required:
        raise ValueError(f"{INPUT_ENV} must contain exactly {sorted(required)}")
    for key in ("gameId", "challengeId", "participationId", "revision"):
        if not isinstance(value[key], int) or isinstance(value[key], bool) or value[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    if not isinstance(value["seed"], str):
        raise ValueError("seed must be a URL-safe base64 string")
    return value


def decode_seed(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    try:
        seed = base64.urlsafe_b64decode(encoded + padding)
    except ValueError as error:
        raise ValueError("seed is not valid URL-safe base64") from error
    if len(seed) != 32:
        raise ValueError("seed must decode to exactly 32 bytes")
    return seed


def generate(value: dict[str, Any]) -> dict[str, Any]:
    material = hashlib.sha256(DOMAIN + decode_seed(value["seed"])).digest()
    left = 1_000 + int.from_bytes(material[0:4], "big") % 9_000
    right = 1_000 + int.from_bytes(material[4:8], "big") % 9_000
    answer = left + right
    manifest = {
        "flag": f"rsctf{{sum_{answer}}}",
        "content": (
            "This challenge was generated deterministically for your team.\n\n"
            f"Add **{left}** and **{right}**, then submit "
            "`rsctf{sum_RESULT}` with the decimal result."
        ),
        "hints": [
            "Only ordinary decimal addition is required.",
            "The receipt field is unused in this example.",
        ],
    }
    canonical = json.dumps(
        manifest,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return {
        "manifest": manifest,
        "artifactSha256": hashlib.sha256(canonical).hexdigest(),
    }


def main() -> int:
    try:
        request = decode_input(os.environ.get(INPUT_ENV, ""))
        output = generate(request)
    except ValueError as error:
        print(f"variant generator: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
