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
import threading
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


def tcp_exchange(port: int, request: bytes) -> bytes:
    """Send one request and read one bounded line from the raw-TCP demo."""
    with socket.create_connection(("127.0.0.1", port), timeout=1) as connection:
        connection.settimeout(1)
        connection.sendall(request)
        connection.shutdown(socket.SHUT_WR)
        response = bytearray()
        while b"\n" not in response and len(response) <= 4096:
            chunk = connection.recv(4097 - len(response))
            if chunk == b"":
                break
            response.extend(chunk)
    return bytes(response)


def test_managed_tcp_protocol(port: int, flag_file: Path, expected_flag: str) -> None:
    expected = {
        b"PING\n": b"PONG\n",
        b"GET_FLAG\n": (expected_flag + "\n").encode(),
        b"UNKNOWN\n": b"ERR unknown command\n",
        b"PING": b"ERR malformed command\n",
        b"\xff\n": b"ERR malformed command\n",
    }
    for request, response in expected.items():
        actual = tcp_exchange(port, request)
        if actual != response:
            raise RuntimeError(
                f"raw TCP request {request!r} returned {actual!r}; expected {response!r}"
            )

    rotated_flag = "rsctf{managed_rotated_smoke_test}"
    flag_file.write_text(rotated_flag + "\n", encoding="utf-8")
    if tcp_exchange(port, b"GET_FLAG\n") != (rotated_flag + "\n").encode():
        raise RuntimeError("raw TCP service cached the previous round's flag")
    flag_file.write_text(expected_flag + "\n", encoding="utf-8")


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


@contextmanager
def imported_checker(checker: Path):
    """Import one checker with its sibling lib.py isolated as module `lib`."""
    previous_library = sys.modules.pop("lib", None)
    checker_directory = str(checker.parent)
    module_name = "rsctf_checker_" + "_".join(
        part.replace("-", "_") for part in checker.relative_to(ROOT).parts
    )
    sys.path.insert(0, checker_directory)
    previous_bytecode_setting = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(module_name, checker)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"could not import {checker}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        library = sys.modules.get("lib")
        if library is None:
            raise RuntimeError(f"{checker} did not import its sibling lib.py")
        yield module, library
    finally:
        sys.dont_write_bytecode = previous_bytecode_setting
        sys.path.remove(checker_directory)
        sys.modules.pop(module_name, None)
        sys.modules.pop("lib", None)
        if previous_library is not None:
            sys.modules["lib"] = previous_library


def fisher_yates_order(items: list[object], selections: list[int]) -> list[object]:
    shuffled = list(items)
    if len(selections) != max(0, len(shuffled) - 1):
        raise RuntimeError("invalid deterministic shuffle plan")
    for index, selected in zip(
        range(len(shuffled) - 1, 0, -1),
        selections,
        strict=True,
    ):
        if selected < 0 or selected > index:
            raise RuntimeError("deterministic shuffle index is out of range")
        shuffled[index], shuffled[selected] = shuffled[selected], shuffled[index]
    return shuffled


def exercise_registered_suite(
    checker: Path,
    runner_name: str,
    environment: dict[str, str],
) -> None:
    """Run every real registered check in two deterministic shuffled orders."""
    with imported_checker(checker) as (module, library):
        functions = list(library._registered_checkers)
        if len(functions) < 2:
            raise RuntimeError(f"{checker.relative_to(ROOT)} must register two checks")

        calls: list[str] = []
        wrapped = []
        for function in functions:
            def record(context, current=function):
                calls.append(current.__name__)
                return current(context)

            wrapped.append(record)

        library._registered_checkers[:] = wrapped
        registry_snapshot = tuple(library._registered_checkers)
        plans = [
            list(range(len(wrapped) - 1, 0, -1)),
            [0] * (len(wrapped) - 1),
        ]
        for selections in plans:
            calls.clear()
            expected = [
                functions[wrapped.index(function)].__name__
                for function in fisher_yates_order(wrapped, selections)
            ]
            with (
                patch.object(library.secrets, "randbelow", side_effect=selections) as random,
                patch.dict(os.environ, environment, clear=True),
            ):
                verdict = getattr(module, runner_name)()
            if verdict != 0:
                raise RuntimeError(f"registered checker suite returned verdict {verdict}")
            if calls != expected:
                raise RuntimeError(f"checker suite order {calls!r} did not match {expected!r}")
            bounds = [call.args[0] for call in random.call_args_list]
            if bounds != list(range(len(wrapped), 1, -1)):
                raise RuntimeError(f"Fisher-Yates bounds were incorrect: {bounds!r}")
            if tuple(library._registered_checkers) != registry_snapshot:
                raise RuntimeError("checker runner mutated registration order")
            if len(calls) != len(functions) or set(calls) != {
                function.__name__ for function in functions
            }:
                raise RuntimeError("checker runner omitted or repeated a registered check")

        library._registered_checkers[:] = functions


def expect_suite_response(
    checker: Path,
    response: bytes,
    expected_verdict: int,
    *,
    team_id: int,
    flag: str,
) -> None:
    """Serve the same synthetic response to both registered checker requests."""
    connection_count = 2
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(connection_count)
    listener.settimeout(5)
    port = listener.getsockname()[1]
    errors: list[BaseException] = []

    def serve() -> None:
        try:
            with listener:
                for _index in range(connection_count):
                    connection, _address = listener.accept()
                    with connection:
                        connection.settimeout(1)
                        connection.recv(4096)
                        if response:
                            connection.sendall(response)
        except BaseException as error:  # surfaced on the main test thread below
            errors.append(error)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    expect(
        checker,
        expected_verdict,
        checker_environment(port, team_id=team_id, flag=flag),
    )
    thread.join(timeout=5)
    if thread.is_alive():
        raise RuntimeError("synthetic checker target did not finish")
    if errors:
        raise RuntimeError(f"synthetic checker target failed: {errors[0]!r}")


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

    module._registered_checkers.clear()
    calls: list[str] = []

    @module.checker
    def registered_success(_context):
        calls.append("success")

    @module.checker
    def registered_second_success(_context):
        calls.append("second success")

    @module.checker
    def registered_mumble(_context):
        calls.append("mumble")
        raise module.Mumble("unexpected response")

    @module.checker
    def registered_offline(_context):
        calls.append("offline")
        raise module.Offline("connection failed")

    @module.checker
    def registered_invalid_return(_context):
        calls.append("invalid return")
        return "invalid"

    @module.checker
    def registered_error(_context):
        calls.append("error")
        raise RuntimeError("checker bug")

    def assert_suite(functions, expected_verdict):
        module._registered_checkers[:] = functions
        registry_snapshot = tuple(module._registered_checkers)
        plans = [
            list(range(len(functions) - 1, 0, -1)),
            [0] * (len(functions) - 1),
        ]
        for selections in plans:
            calls.clear()
            expected_order = [
                function.__name__.removeprefix("registered_").replace("_", " ")
                for function in fisher_yates_order(functions, selections)
            ]
            with (
                patch.object(module.secrets, "randbelow", side_effect=selections) as random,
                patch.dict(os.environ, environment, clear=True),
            ):
                verdict = module.run_ad_checker()
            if verdict != expected_verdict:
                raise RuntimeError(
                    f"checker suite returned {verdict}; expected {expected_verdict}"
                )
            if calls != expected_order:
                raise RuntimeError(
                    f"checker suite omitted or reordered calls: {calls!r} != {expected_order!r}"
                )
            if tuple(module._registered_checkers) != registry_snapshot:
                raise RuntimeError("checker suite mutated registration order")
            bounds = [call.args[0] for call in random.call_args_list]
            if bounds != list(range(len(functions), 1, -1)):
                raise RuntimeError(f"checker suite used invalid shuffle bounds: {bounds!r}")

    suites = [
        ([registered_success, registered_second_success], 0),
        ([registered_success, registered_mumble, registered_second_success], 1),
        ([registered_mumble, registered_offline, registered_success], 2),
        ([registered_mumble, registered_error, registered_offline, registered_success], 3),
        ([registered_invalid_return, registered_offline, registered_success], 3),
    ]
    for functions, expected_verdict in suites:
        assert_suite(functions, expected_verdict)

    module._registered_checkers[:] = [registered_success, registered_second_success]
    with patch.dict(os.environ, environment, clear=True):
        with patch.object(module.secrets, "randbelow", side_effect=RuntimeError("shuffle")):
            if module.run_ad_checker() != 3:
                raise RuntimeError("checker shuffle errors must return InternalError")

        module._registered_checkers.clear()
        if module.run_ad_checker() != 3:
            raise RuntimeError("an empty checker registry must return InternalError")

    @module.checker
    def registered_koth_success(context):
        if context.__class__.__name__ != "KothContext":
            raise RuntimeError("KotH runner loaded the wrong context")

    koth_environment = checker_environment(1, team_id=0)

    @module.koth_checker
    def legacy_koth_success(_context):
        return None

    with patch.dict(os.environ, koth_environment, clear=True):
        if module.run_koth_checker() != 0:
            raise RuntimeError("registered KotH checker did not return OK")
        if legacy_koth_success() != 0:
            raise RuntimeError("legacy @koth_checker did not return OK")


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

            test_managed_tcp_protocol(
                managed_port,
                managed_flag_file,
                managed_flag,
            )

            managed_checker = managed / "checker/run.py"
            byoc_checker = byoc / "checker/run.py"
            koth_checker = koth / "checker/run.py"
            exercise_registered_suite(
                managed_checker,
                "run_ad_checker",
                checker_environment(managed_port, team_id=1, flag=managed_flag),
            )
            exercise_registered_suite(
                byoc_checker,
                "run_ad_checker",
                checker_environment(byoc_port, team_id=2, flag=byoc_flag),
            )
            exercise_registered_suite(
                koth_checker,
                "run_koth_checker",
                checker_environment(koth_port, team_id=0),
            )

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
                byoc_checker,
                0,
                checker_environment(byoc_port, team_id=2, flag=byoc_flag),
            )
            expect(
                byoc_checker,
                1,
                checker_environment(byoc_port, team_id=2, flag="wrong"),
            )
            expect(
                byoc_checker,
                2,
                checker_environment(unused_port(), team_id=2, flag=byoc_flag),
            )

            expect_suite_response(
                managed_checker,
                b"partial response",
                1,
                team_id=1,
                flag=managed_flag,
            )
            expect_suite_response(
                managed_checker,
                b"",
                2,
                team_id=1,
                flag=managed_flag,
            )
            expect_suite_response(
                managed_checker,
                b"x" * 4097 + b"\n",
                1,
                team_id=1,
                flag=managed_flag,
            )
            expect_suite_response(
                byoc_checker,
                b"not http\r\n\r\n",
                1,
                team_id=2,
                flag=byoc_flag,
            )
            expect_suite_response(
                byoc_checker,
                b"HTTP/1.1 302 Found\r\nContent-Length: 0\r\n\r\n",
                1,
                team_id=2,
                flag=byoc_flag,
            )
            oversized_body = b"x" * 4097
            expect_suite_response(
                byoc_checker,
                (
                    b"HTTP/1.1 200 OK\r\n"
                    + f"Content-Length: {len(oversized_body)}\r\n\r\n".encode()
                    + oversized_body
                ),
                1,
                team_id=2,
                flag=byoc_flag,
            )
            expect(
                koth_checker,
                0,
                checker_environment(koth_port, team_id=0),
            )
            expect(
                koth_checker,
                3,
                checker_environment(koth_port, team_id=0, flag="not-for-koth"),
            )
            expect(
                koth_checker,
                3,
                checker_environment(koth_port, team_id=0, flag=""),
            )
            expect(
                koth_checker,
                3,
                checker_environment(koth_port, team_id=1),
            )

    print("OK: raw TCP, HTTP, registered checker suites, and verdicts passed.")


if __name__ == "__main__":
    main()
