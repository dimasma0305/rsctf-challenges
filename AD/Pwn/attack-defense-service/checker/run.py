"""Dependency-free rsctf A&D checker.

Exit codes follow the current rsctf/enochecker-style contract:
0 = OK, 1 = Mumble, 2 = Offline, 3 = InternalError.
"""

import os
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def fetch(url: str) -> str:
    with urlopen(url, timeout=5) as response:  # nosec B310 - target is provided by rsctf
        return response.read(1024).decode("utf-8").strip()


def main() -> int:
    try:
        host = os.environ["RSCTF_TARGET_IP"].strip()
        port = int(os.environ["RSCTF_TARGET_PORT"])
        flag = os.environ["RSCTF_FLAG"]
    except (KeyError, TypeError, ValueError):
        return 3

    if not host or not 1 <= port <= 65535 or not flag:
        return 3

    base = f"http://{host}:{port}"
    try:
        planted = fetch(f"{base}/plant?{urlencode({'flag': flag})}")
        if planted != "ok":
            return 1
        return 0 if fetch(f"{base}/flag") == flag else 1
    except HTTPError:
        return 1
    except (URLError, TimeoutError, ConnectionError, socket.timeout, OSError):
        return 2
    except Exception:  # Defensive: checker bugs must not penalize the target team.
        return 3


raise SystemExit(main())
