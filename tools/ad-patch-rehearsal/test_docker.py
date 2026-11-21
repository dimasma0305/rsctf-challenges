"""Run five hosted services per team and exercise real checker processes for two rounds."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import uuid

from generate import EXERCISES, generate
from test_rehearsal import verdict


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, timeout=180).strip()


def check(teams):
    prefix = f"rsctf-rehearsal-{uuid.uuid4().hex[:12]}"
    with tempfile.TemporaryDirectory() as directory, ExitStack() as cleanup:
        event = Path(directory) / "event"
        generate(event)
        services = []
        for exercise in EXERCISES:
            pkg = event / "repository/challenges/AD/Web" / exercise.name
            image = f"{prefix}:{exercise.name}"
            docker("build", "--network=none", "-t", image, pkg / "src")
            cleanup.callback(docker, "image", "rm", image)
            for _ in range(teams):
                container = docker("run", "-d", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                                   "--cpus=1", "--memory=64m", "--pids-limit=32",
                                   "-p", "127.0.0.1::8080", image)
                cleanup.callback(docker, "rm", "-fv", container)
                port = int(docker("port", container, "8080/tcp").rsplit(":", 1)[1])
                services.append((container, port, pkg / "checker/run.py"))
        deadline = time.monotonic() + 75
        for container, _, _ in services:
            while docker("inspect", "--format", "{{.State.Health.Status}}", container) != "healthy":
                if time.monotonic() >= deadline:
                    raise RuntimeError("service health check timed out")
                time.sleep(1)
        checks = 0
        for _ in range(2):
            for container, port, checker in services:
                flag = f"flag{{{secrets.token_hex(16)}}}"
                subprocess.run(["docker", "exec", "-i", container, "sh", "-c", "cat > /flag"],
                               input=flag, text=True, check=True, timeout=5)
                if verdict(checker, port, flag) != 0:
                    raise RuntimeError(f"checker failed for {checker.parents[1].name}")
                checks += 1
        print(json.dumps({"teams": teams, "healthyContainers": len(services), "successfulChecks": checks}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teams", type=int, choices=range(1, 6), default=5)
    check(parser.parse_args().teams)
