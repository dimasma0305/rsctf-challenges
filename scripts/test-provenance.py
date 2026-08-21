#!/usr/bin/env python3
"""Exercise the deterministic variant-generator contract without Docker."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "Jeopardy/Misc/deterministic-variant/generator/generate.py"


def encoded_request(seed: bytes) -> str:
    request = {
        "gameId": 7,
        "challengeId": 11,
        "participationId": 23,
        "revision": 1,
        "seed": base64.urlsafe_b64encode(seed).decode().rstrip("="),
    }
    return base64.urlsafe_b64encode(
        json.dumps(request, separators=(",", ":")).encode()
    ).decode().rstrip("=")


def run(seed: bytes) -> tuple[bytes, dict[str, object]]:
    environment = os.environ.copy()
    environment["RSCTF_VARIANT_INPUT"] = encoded_request(seed)
    completed = subprocess.run(
        [sys.executable, "-I", str(GENERATOR)],
        check=True,
        capture_output=True,
        env=environment,
        timeout=5,
    )
    return completed.stdout, json.loads(completed.stdout)


def main() -> int:
    first_bytes, first = run(bytes(range(32)))
    repeated_bytes, repeated = run(bytes(range(32)))
    changed_bytes, changed = run(bytes(reversed(range(32))))

    assert first_bytes == repeated_bytes
    assert first == repeated
    assert first_bytes != changed_bytes
    assert first["manifest"]["flag"].startswith("rsctf{sum_")
    assert first["manifest"]["flag"] != changed["manifest"]["flag"]
    assert "seed" not in first_bytes.decode().lower()

    canonical = json.dumps(
        first["manifest"],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    assert first["artifactSha256"] == hashlib.sha256(canonical).hexdigest()
    print("OK: deterministic variant generator output and artifact hash verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
