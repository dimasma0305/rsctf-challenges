#!/usr/bin/env python3
"""Exercise a built example image through Docker's real health lifecycle."""

from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import tempfile
import time
import uuid


PUBLIC_TEST_FLAG = "rsctf{container_smoke_public}"
MAX_RESPONSE_BYTES = 4096
STATIC_FLAG_SERVICE = "jeopardy-web-static-flag-service"
DYNAMIC_FLAG_SERVICE = "jeopardy-web-dynamic-flag-service"
ATTACK_DEFENSE_SERVICE = "ad-pwn-attack-defense-service"
SELF_HOSTED_SERVICE = "ad-web-self-hosted-service"
KING_OF_THE_HILL = "koth-pwn-king-of-the-hill"
API_OBSERVED_HILL = "koth-web-api-observed-hill"
CASES = {
    STATIC_FLAG_SERVICE,
    DYNAMIC_FLAG_SERVICE,
    ATTACK_DEFENSE_SERVICE,
    SELF_HOSTED_SERVICE,
    KING_OF_THE_HILL,
    API_OBSERVED_HILL,
}
SMOKE_LABEL = "org.rsctf.example-smoke"


def docker(
    command: list[str], *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*command, *arguments],
        check=check,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )


def http_request(
    port: int,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise RuntimeError(f"{method} {path} response exceeded {MAX_RESPONSE_BYTES} bytes")
        return response.status, payload
    finally:
        connection.close()


def require_http(port: int, path: str, expected: bytes) -> None:
    status, body = http_request(port, "GET", path)
    if status != 200 or body != expected:
        raise RuntimeError(
            f"GET {path} returned status={status}, body={body[:160]!r}; expected 200/{expected!r}"
        )


def smoke(case: str, port: int) -> None:
    if case == ATTACK_DEFENSE_SERVICE:
        with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
            connection.sendall(b"PING\n")
            if connection.makefile("rb").readline(MAX_RESPONSE_BYTES + 1) != b"PONG\n":
                raise RuntimeError("raw TCP PING did not return PONG")
        with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
            connection.sendall(b"GET_FLAG\n")
            if connection.makefile("rb").readline(MAX_RESPONSE_BYTES + 1) != (
                PUBLIC_TEST_FLAG + "\n"
            ).encode():
                raise RuntimeError("raw TCP GET_FLAG did not return the current test flag")
        return

    require_http(port, "/health", b"ok\n")
    if case == STATIC_FLAG_SERVICE:
        require_http(port, "/", f"Shared rsctf demo service\n{PUBLIC_TEST_FLAG}\n".encode())
    elif case == DYNAMIC_FLAG_SERVICE:
        require_http(port, "/", f"Personal rsctf demo service\n{PUBLIC_TEST_FLAG}\n".encode())
    elif case == SELF_HOSTED_SERVICE:
        require_http(port, "/secret", (PUBLIC_TEST_FLAG + "\n").encode())
    elif case == KING_OF_THE_HILL:
        require_http(
            port,
            "/",
            b"rsctf KotH demo: submit your token at /claim?token=...\n",
        )
        require_http(port, "/claim?token=koth_container_smoke", b"claim recorded\n")
    elif case == API_OBSERVED_HILL:
        require_http(
            port,
            "/",
            b"rsctf Leaderboard KotH: solve one-use puzzles; every team can score\n",
        )
        request = json.dumps({"token": "koth_container_smoke"}, separators=(",", ":")).encode()
        status, body = http_request(
            port,
            "POST",
            "/start",
            request,
            {"Content-Type": "application/json", "Content-Length": str(len(request))},
        )
        response = json.loads(body)
        required = {"algorithm", "difficulty", "expiresAt", "maxCounter", "nonce", "sessionId"}
        if status != 201 or set(response) != required or response["difficulty"] != 4:
            raise RuntimeError(f"POST /start returned an invalid puzzle: status={status}, body={body!r}")


def published_port(command: list[str], container: str) -> int:
    output = docker(command, "port", container, "8080/tcp").stdout.strip()
    endpoint = output.splitlines()[0] if output else ""
    try:
        host, raw_port = endpoint.rsplit(":", 1)
        port = int(raw_port)
    except (ValueError, IndexError) as error:
        raise RuntimeError(f"Docker returned an invalid published port: {output!r}") from error
    if host != "127.0.0.1" or not 1 <= port <= 65535:
        raise RuntimeError(f"Docker returned an unsafe published endpoint: {endpoint!r}")
    return port


def wait_healthy(command: list[str], container: str) -> None:
    deadline = time.monotonic() + 35
    last = "unknown"
    while time.monotonic() < deadline:
        result = docker(
            command,
            "inspect",
            "--format",
            "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}",
            container,
        )
        last = result.stdout.strip()
        if last == "running healthy":
            return
        if last.startswith(("exited ", "dead ")) or last.endswith(" unhealthy"):
            break
        time.sleep(0.5)
    raise RuntimeError(f"container did not become healthy; final Docker state was {last!r}")


def remove_owned_container(command: list[str], container: str, ownership: str) -> None:
    result = docker(
        command,
        "inspect",
        "--format",
        f'{{{{.Name}}}} {{{{index .Config.Labels "{SMOKE_LABEL}"}}}}',
        container,
        check=False,
    )
    if result.returncode != 0:
        return
    if result.stdout.strip() != f"/{container} {ownership}":
        raise RuntimeError(
            f"refusing to remove Docker container {container!r}: ownership label mismatch"
        )
    docker(command, "rm", "--force", container)


def run(command: list[str], image: str, case: str) -> None:
    ownership = uuid.uuid4().hex
    container = f"rsctf-example-smoke-{ownership}"
    with tempfile.TemporaryDirectory(prefix="rsctf-example-container-") as temporary:
        flag_path = Path(temporary, "flag")
        flag_path.write_text(PUBLIC_TEST_FLAG + "\n", encoding="utf-8")
        arguments = [
            "run",
            "--detach",
            "--name",
            container,
            "--label",
            f"{SMOKE_LABEL}={ownership}",
            "--publish",
            "127.0.0.1::8080",
        ]
        if case in {STATIC_FLAG_SERVICE, DYNAMIC_FLAG_SERVICE}:
            arguments.extend(["--env", f"RSCTF_FLAG={PUBLIC_TEST_FLAG}"])
        if case in {ATTACK_DEFENSE_SERVICE, SELF_HOSTED_SERVICE}:
            arguments.extend(
                [
                    "--mount",
                    f"type=bind,source={flag_path},target=/run/rsctf/flag,readonly",
                ]
            )
        arguments.append(image)

        try:
            docker(command, *arguments)
            wait_healthy(command, container)
            smoke(case, published_port(command, container))
        finally:
            remove_owned_container(command, container, ownership)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-cases", action="store_true")
    parser.add_argument("--image")
    parser.add_argument("--case", choices=sorted(CASES))
    parser.add_argument("--docker", default=os.environ.get("DOCKER", "docker"))
    arguments = parser.parse_args()
    if arguments.list_cases:
        if arguments.image is not None or arguments.case is not None:
            parser.error("--list-cases cannot be combined with --image or --case")
        print(json.dumps(sorted(CASES), separators=(",", ":")))
        return
    if arguments.image is None or arguments.case is None:
        parser.error("--image and --case are required unless --list-cases is used")
    if not arguments.image.strip() or any(character.isspace() for character in arguments.image):
        parser.error("--image must be one non-empty Docker image reference")
    command = shlex.split(arguments.docker)
    if not command:
        parser.error("--docker must name a Docker-compatible command")
    run(command, arguments.image, arguments.case)
    print(f"OK: {arguments.case} image became healthy and passed its functional smoke test.")


if __name__ == "__main__":
    main()
