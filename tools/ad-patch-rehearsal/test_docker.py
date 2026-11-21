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
        services = {}
        for challenge, exercise in enumerate(EXERCISES, 1):
            pkg = event / "repository/challenges/AD/Web" / exercise.name
            image = f"{prefix}:{exercise.name}"
            docker("build", "--network=none", "-t", image, pkg / "src")
            cleanup.callback(docker, "image", "rm", image)
            for team in range(1, teams + 1):
                container = docker("run", "-d", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                                   "--cpus=1", "--memory=64m", "--pids-limit=32",
                                   "-p", "127.0.0.1::8080", image)
                cleanup.callback(docker, "rm", "-fv", container)
                port = int(docker("port", container, "8080/tcp").rsplit(":", 1)[1])
                services[challenge, team] = (container, port, pkg / "checker/run.py")
        deadline = time.monotonic() + 75
        for container, _, _ in services.values():
            while docker("inspect", "--format", "{{.State.Health.Status}}", container) != "healthy":
                if time.monotonic() >= deadline:
                    raise RuntimeError("service health check timed out")
                time.sleep(1)
        checks = 0
        rejected = 0
        flags = {}
        for round_number in (1, 2):
            previous = flags
            flags = {key: f"flag{{{secrets.token_hex(16)}}}" for key in services}
            # Deliver the entire round before checking any service. Interleaving
            # writes with reads could hide a flag file shared between teams.
            for key, (container, _, _) in services.items():
                subprocess.run(["docker", "exec", "-i", container, "sh", "-c", "cat > /flag"],
                               input=flags[key], text=True, check=True, timeout=5)
            for (challenge, team), (_, port, checker) in services.items():
                key = challenge, team
                ctx = dict(challenge_id=challenge, team_id=team, round_number=round_number)
                if verdict(checker, port, flags[key], **ctx) != 0:
                    raise RuntimeError(f"current round check failed for challenge {challenge}, team {team}")
                checks += 1
                wrong_flags = []
                if previous:
                    wrong_flags.append(previous[key])
                if teams > 1:
                    wrong_flags.append(flags[challenge, team % teams + 1])
                for wrong_flag in wrong_flags:
                    if verdict(checker, port, wrong_flag, **ctx) != 1:
                        raise RuntimeError(f"expected a flag mismatch for challenge {challenge}, team {team}")
                    rejected += 1
        print(json.dumps({"teams": teams, "healthyContainers": len(services), "successfulChecks": checks,
                          "expectedFlagMismatches": rejected}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teams", type=int, choices=range(1, 6), default=5)
    check(parser.parse_args().teams)
