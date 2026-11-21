"""Exercise team storage and both rollbacks in a disposable single-node Kind cluster."""
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import select
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

from generate import generate
from test_rehearsal import installation_id, verdict


NODE_IMAGE = "kindest/node:v1.36.1@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5"


def run(*args, env=None, payload=None, timeout=90):
    return subprocess.run(args, env=env, input=payload, text=True, check=True,
                          stdout=subprocess.PIPE, timeout=timeout).stdout.strip()


def build_images(root, name, cleanup):
    event = root / "event"
    generate(event)
    package = event / "repository/challenges/AD/Web/order-total"
    dockerfile = (package / "src/Dockerfile").read_text()
    images = {}
    for version in ("starter", "patched", "patched-v2"):
        context = root / version
        with ZipFile(event / f"patches/order-total/{version}.zip") as archive:
            archive.extractall(context)
        buildfile = context / "Dockerfile"
        if buildfile.read_text() != "FROM rsctf-starter\n" + dockerfile.split("\n", 1)[1]:
            raise ValueError("offline patch and hosted example use different build instructions")
        buildfile.write_text(dockerfile)
        image = f"{name}:{version}"
        run("docker", "build", "--network=none", "-t", image, str(context), timeout=240)
        cleanup.callback(run, "docker", "image", "rm", image)
        images[version] = image
    return images, package / "checker/run.py"


@contextmanager
def forwarded(kubectl, team):
    with subprocess.Popen([*kubectl, "port-forward", "--address=127.0.0.1", f"service/{team}", ":8080"],
                          stdout=subprocess.PIPE, text=True) as process:
        try:
            if not select.select([process.stdout], [], [], 30)[0]:
                raise TimeoutError("team service port-forward timed out")
            match = re.fullmatch(r"Forwarding from 127\.0\.0\.1:(\d+) -> 8080", process.stdout.readline().strip())
            if not match:
                raise RuntimeError("team service port-forward failed")
            yield int(match[1])
        finally:
            process.terminate()


def check(root, cleanup):
    name = "rsctf-patch-" + secrets.token_hex(6)
    images, checker = build_images(root, name, cleanup)
    config = str(root / "kubeconfig")
    env = {**os.environ, "KUBECONFIG": config}
    cleanup.callback(run, "kind", "delete", "cluster", "--name", name, env=env)
    run("kind", "create", "cluster", "--name", name, "--image", NODE_IMAGE, "--wait", "2m",
        env=env, timeout=300)
    run("kind", "load", "docker-image", "--name", name, *images.values(), env=env, timeout=180)
    kube = ["kubectl", "--kubeconfig", config, "--context", f"kind-{name}"]

    def create(kind, team, spec, labels=None):
        resource = {"apiVersion": "v1", "kind": kind, "metadata": {"name": team}, "spec": spec}
        if labels:
            resource["metadata"]["labels"] = labels
        run(*kube, "create", "-f", "-", payload=json.dumps(resource))

    def pod(team, version, persistent=True):
        container = {"name": "service", "image": images[version], "imagePullPolicy": "Never",
                     "readinessProbe": {"httpGet": {"path": "/health", "port": 8080}, "periodSeconds": 1},
                     "securityContext": {"runAsNonRoot": True, "runAsUser": 65534,
                                         "allowPrivilegeEscalation": False, "capabilities": {"drop": ["ALL"]}}}
        spec = {"containers": [container], "automountServiceAccountToken": False}
        if persistent:
            spec["volumes"] = [{"name": "data", "persistentVolumeClaim": {"claimName": team}}]
            container["volumeMounts"] = [{"name": "data", "mountPath": "/var/lib/rehearsal"}]
        create("Pod", team, spec, {"team": team})
        run(*kube, "wait", "--for=condition=Ready", f"pod/{team}", "--timeout=75s")

    def remove_pod(team):
        run(*kube, "delete", "pod", team, "--wait=true", "--timeout=60s", "--grace-period=1")

    def deliver(team, flag):
        run(*kube, "exec", "-i", team, "--", "sh", "-ec", "cat > /flag", payload=flag)

    for team in ("team-one", "team-two", "ephemeral"):
        create("Service", team, {"selector": {"team": team}, "ports": [{"port": 8080, "targetPort": 8080}]})
        if team != "ephemeral":
            create("PersistentVolumeClaim", team, {"accessModes": ["ReadWriteOnce"],
                   "resources": {"requests": {"storage": "32Mi"}}})

    # Negative control: an image VOLUME declaration does not retain a team's
    # SQLite record between two independently created Kubernetes Pods.
    pod("ephemeral", "starter", persistent=False)
    with forwarded(kube, "ephemeral") as port:
        original = installation_id(port)
    remove_pod("ephemeral")
    pod("ephemeral", "starter", persistent=False)
    with forwarded(kube, "ephemeral") as port:
        assert installation_id(port) != original

    peer_flag = secrets.token_hex(24)
    pod("team-two", "starter")
    deliver("team-two", peer_flag)
    service = run(*kube, "get", "svc/team-one", "-o", "jsonpath={.metadata.uid}/{.spec.clusterIP}")
    first_id = None
    with forwarded(kube, "team-two") as peer_port:
        peer_id = installation_id(peer_port)
        for step, version in enumerate(("starter", "patched", "patched-v2", "patched", "starter"), 1):
            if step > 1:
                remove_pod("team-one")
            pod("team-one", version)
            run(*kube, "exec", "team-one", "--", "test", "!", "-s", "/flag")
            flag = secrets.token_hex(24)
            deliver("team-one", flag)
            with forwarded(kube, "team-one") as port:
                current = installation_id(port)
                first_id = first_id or current
                assert current == first_id and current != peer_id
                assert verdict(checker, port, flag, round_number=step) == 0
                assert verdict(checker, port, peer_flag, round_number=step) == 1
                for value in ([], None):
                    req = Request(f"http://127.0.0.1:{port}/evaluate", data=json.dumps(value).encode())
                    try:
                        with urlopen(req, timeout=3) as response:
                            assert json.load(response) == (None if version == "starter" else 0)
                            assert value is not None or version != "patched"
                    except HTTPError as error:
                        with error:
                            assert error.code == 400 and value is None and version == "patched"
            assert installation_id(peer_port) == peer_id
            assert verdict(checker, peer_port, peer_flag, team_id=2, round_number=step) == 0
            assert run(*kube, "get", "svc/team-one", "-o", "jsonpath={.metadata.uid}/{.spec.clusterIP}") == service
    print("Unclaimed storage lost the installation ID. Two separate team claims preserved their data, "
          "fresh flags and Service identity across both repairs and both rollbacks.")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory, ExitStack() as cleanup:
        check(Path(directory), cleanup)
