#!/usr/bin/env python3
"""Run the bundled A&D/KotH checkers against their example services."""

from contextlib import ExitStack, contextmanager
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def unused_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_for_service(process: subprocess.Popen[bytes], port: int) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.communicate()[0].decode(errors="replace")
            raise RuntimeError(f"service exited before listening:\n{output}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"service did not listen on port {port}")


@contextmanager
def service(package: Path, port: int, **environment: str):
    process_environment = os.environ.copy()
    process_environment.update(environment)
    process_environment.update(
        PORT=str(port),
        PYTHONDONTWRITEBYTECODE="1",
    )
    process = subprocess.Popen(
        [PYTHON, "src/app.py"],
        cwd=package,
        env=process_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_service(process, port)
        yield
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def checker_environment(port: int, *, team_id: int, flag: str | None = None):
    environment = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "RSCTF_ACTION": "check",
        "RSCTF_TARGET_IP": "127.0.0.1",
        "RSCTF_TARGET_PORT": str(port),
        "RSCTF_ROUND": "1",
        "RSCTF_TEAM_ID": str(team_id),
        "RSCTF_CHALLENGE_ID": "1",
    }
    if flag is not None:
        environment["RSCTF_FLAG"] = flag
    return environment


def expect(checker: Path, expected: int, environment: dict[str, str]) -> None:
    result = subprocess.run(
        [PYTHON, checker],
        cwd=checker.parent.parent,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=5,
        check=False,
    )
    if result.returncode != expected:
        output = result.stdout.decode(errors="replace")
        relative = checker.relative_to(ROOT)
        raise RuntimeError(
            f"{relative} exited {result.returncode}; expected {expected}\n{output}"
        )


def test_decorator_guardrails(library: Path) -> None:
    """The framework must map outcomes without assuming a service protocol."""
    module_name = "rsctf_checker_template_lib"
    spec = importlib.util.spec_from_file_location(module_name, library)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {library}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    @module.ad_checker
    def succeeds(_context):
        return None

    @module.ad_checker
    def mumbles(_context):
        raise module.Mumble("unexpected response")

    @module.ad_checker
    def is_offline(_context):
        raise module.Offline("connection failed")

    @module.ad_checker
    def exits(_context):
        raise SystemExit(1)

    @module.ad_checker
    def returns_a_value(_context):
        return "invalid"

    environment = checker_environment(1, team_id=1, flag="rsctf{guardrail}")
    with patch.dict(os.environ, environment, clear=True):
        actual = {
            "success": succeeds(),
            "mumble": mumbles(),
            "offline": is_offline(),
            "system exit": exits(),
            "invalid return": returns_a_value(),
        }
    expected = {
        "success": 0,
        "mumble": 1,
        "offline": 2,
        "system exit": 3,
        "invalid return": 3,
    }
    if actual != expected:
        raise RuntimeError(f"checker decorator verdict mismatch: {actual!r}")


def main() -> None:
    managed = ROOT / "AD/Pwn/attack-defense-service"
    byoc = ROOT / "AD/Web/self-hosted-service"
    koth = ROOT / "Koth/Pwn/king-of-the-hill"
    test_decorator_guardrails(managed / "checker/lib.py")

    with tempfile.TemporaryDirectory(prefix="rsctf-checkers-") as temporary:
        temporary_root = Path(temporary)
        managed_flag = "rsctf{managed_smoke_test}"
        byoc_flag = "rsctf{byoc_smoke_test}"
        managed_flag_file = temporary_root / "managed.flag"
        byoc_flag_file = temporary_root / "byoc.flag"
        managed_flag_file.write_text(managed_flag + "\n", encoding="utf-8")
        byoc_flag_file.write_text(byoc_flag + "\n", encoding="utf-8")

        ports: set[int] = set()
        while len(ports) < 3:
            ports.add(unused_port())
        managed_port, byoc_port, koth_port = ports
        with ExitStack() as stack:
            stack.enter_context(
                service(
                    managed,
                    managed_port,
                    RSCTF_FLAG_FILE=str(managed_flag_file),
                )
            )
            stack.enter_context(
                service(byoc, byoc_port, RSCTF_FLAG_FILE=str(byoc_flag_file))
            )
            stack.enter_context(
                service(
                    koth,
                    koth_port,
                    KOTH_KING_PATH=str(temporary_root / "king"),
                )
            )

            managed_checker = managed / "checker/run.py"
            expect(
                managed_checker,
                0,
                checker_environment(managed_port, team_id=1, flag=managed_flag),
            )
            expect(
                managed_checker,
                1,
                checker_environment(managed_port, team_id=1, flag="wrong"),
            )
            expect(
                managed_checker,
                2,
                checker_environment(unused_port(), team_id=1, flag=managed_flag),
            )
            expect(
                managed_checker,
                3,
                checker_environment(managed_port, team_id=1),
            )
            expect(managed_checker, 3, {})

            expect(
                byoc / "checker/run.py",
                0,
                checker_environment(byoc_port, team_id=2, flag=byoc_flag),
            )
            expect(
                koth / "checker/run.py",
                0,
                checker_environment(koth_port, team_id=0),
            )
            expect(
                koth / "checker/run.py",
                3,
                checker_environment(koth_port, team_id=0, flag="not-for-koth"),
            )
            expect(
                koth / "checker/run.py",
                3,
                checker_environment(koth_port, team_id=0, flag=""),
            )
            expect(
                koth / "checker/run.py",
                3,
                checker_environment(koth_port, team_id=1),
            )

    print("OK: checker smoke tests cover all verdicts and protocol-neutral decorators.")


if __name__ == "__main__":
    main()
