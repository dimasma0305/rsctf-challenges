"""Check the banner and round proof using the RSCTF process-checker contract."""

import hmac
import os
import re
import secrets
from http.client import HTTPConnection, HTTPException
from ipaddress import ip_address


def check():
    try:
        host = str(ip_address(os.environ["RSCTF_TARGET_IP"]))
        port = int(os.environ["RSCTF_TARGET_PORT"])
        flag = os.environ["RSCTF_FLAG"].encode("ascii")
        if not 1 <= port <= 65535 or not re.fullmatch(rb"flag\{[A-Za-z0-9_-]{32}\}", flag):
            return 3
    except (KeyError, ValueError):
        return 3

    nonce = secrets.token_bytes(16)
    expected = hmac.digest(flag, nonce, "sha256").hex().encode("ascii")
    connection = HTTPConnection(host, port, timeout=2)
    try:
        connection.request("GET", "/")
        banner = connection.getresponse()
        if banner.status != 200 or not 0 < len(banner.read(129)) <= 128:
            return 1
        connection.request("GET", "/proof/" + nonce.hex())
        proof = connection.getresponse()
        if proof.status != 200 or not hmac.compare_digest(proof.read(65), expected):
            return 1
    except (OSError, HTTPException):
        return 2
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    try:
        result = check()
    except Exception:
        result = 3
    raise SystemExit(result)
