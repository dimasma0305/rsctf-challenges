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
from urllib.request import Request, urlopen
import zipfile

from generate import EXERCISES, generate
from test_rehearsal import installation_id, verdict


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, timeout=180).strip()


def start_service(cleanup, image, *storage):
    container = docker("run", "-d", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                       "--cpus=1", "--memory=64m", "--pids-limit=32",
                       *storage, "-p", "127.0.0.1::8080", image)
    cleanup.callback(docker, "rm", "-fv", container)
    port = int(docker("port", container, "8080/tcp").rsplit(":", 1)[1])
    return container, port


def wait_healthy(container, deadline):
    while docker("inspect", "--format", "{{.State.Health.Status}}", container) != "healthy":
        if time.monotonic() >= deadline:
            raise RuntimeError("service health check timed out")
        time.sleep(1)


def check_live_edits(event, services, flags):
    exercise = EXERCISES[0]
    container, port, checker = services[1, 1]
    installation = installation_id(port)

    def evaluate(port, value):
        request = Request(f"http://127.0.0.1:{port}/evaluate", data=json.dumps(value).encode())
        with urlopen(request, timeout=2) as response:
            return json.load(response)

    starter_result = evaluate(port, exercise.edge)
    assert starter_result != exercise.edge_result
    for archive in ("patched", "invalid", "missing-function", "patched-v2"):
        if archive == "invalid":
            source = b"def evaluate(\n"
        elif archive == "missing-function":
            source = b"# edit in progress\n"
        else:
            with zipfile.ZipFile(event / "patches" / exercise.name / f"{archive}.zip") as patch:
                source = patch.read("exercise.py")
        subprocess.run(["docker", "exec", "-i", container, "sh", "-ec",
                        'tmp=$(mktemp /app/.edit.XXXXXX); cat > "$tmp"; '
                        'mv "$tmp" /app/exercise.py; kill -HUP 1'],
                       input=source, check=True, timeout=5)
        assert evaluate(port, exercise.edge) == exercise.edge_result, archive
        if archive == "patched-v2":
            assert evaluate(port, None) == exercise.null_result
        if (1, 2) in services:
            assert evaluate(services[1, 2][1], exercise.edge) == starter_result
        assert installation_id(port) == installation
        assert verdict(checker, port, flags[1, 1], round_number=2) == 0


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
                container, port = start_service(cleanup, image)
                services[challenge, team] = (container, port, pkg / "checker/run.py")
        deadline = time.monotonic() + 75
        installations = {}
        volumes = {}
        for key, (container, port, _) in services.items():
            wait_healthy(container, deadline)
            installations[key] = installation_id(port)
            mounts = json.loads(docker("inspect", "--format", "{{json .Mounts}}", container))
            if len(mounts) != 1 or mounts[0]["Type"] != "volume" or mounts[0]["Destination"] != "/var/lib/rehearsal":
                raise RuntimeError(f"unexpected default service mounts for challenge/team {key}")
            volumes[key] = mounts[0]["Name"]
        if len(set(volumes.values())) != len(services):
            raise RuntimeError("services shared a Docker data volume")
        if len(set(installations.values())) != len(services):
            raise RuntimeError("services shared an installation ID")
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
        check_live_edits(event, services, flags)
        original = services[1, 1][0]
        docker("stop", "-t", "1", original)
        image = docker("inspect", "--format", "{{.Image}}", original)
        replacement, port = start_service(cleanup, image, "--mount",
                                          f"type=volume,source={volumes[1, 1]},target=/var/lib/rehearsal")
        wait_healthy(replacement, time.monotonic() + 30)
        if installation_id(port) != installations[1, 1]:
            raise RuntimeError("the replacement lost the original team's data")
        docker("exec", replacement, "test", "!", "-s", "/flag")
        print(json.dumps({"teams": teams, "healthyContainers": len(services), "successfulChecks": checks,
                          "expectedFlagMismatches": rejected, "distinctInstallations": len(services),
                          "distinctDataVolumes": len(set(volumes.values())), "replacementPreservedData": True,
                          "liveEditsApplied": 2, "invalidEditsKeptPreviousVersion": 2}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teams", type=int, choices=range(1, 6), default=5)
    check(parser.parse_args().teams)
