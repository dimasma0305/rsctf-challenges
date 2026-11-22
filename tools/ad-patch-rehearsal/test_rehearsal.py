"""Exercise the generated services, checker verdicts and team ZIPs on loopback."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import select
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

from generate import EXERCISES, generate


@contextmanager
def service(src, flag_path, state_dir):
    env = {**os.environ, "BIND": "127.0.0.1", "PORT": "0", "RSCTF_FLAG_FILE": str(flag_path),
           "REHEARSAL_DATA_DIR": str(state_dir)}
    with subprocess.Popen([sys.executable, "-B", "server.py"], cwd=src, env=env,
                          stdout=subprocess.PIPE, text=True) as proc:
        try:
            if not select.select([proc.stdout], [], [], 5)[0]:
                raise RuntimeError("service startup timed out")
            yield int(proc.stdout.readline())
        finally:
            proc.kill()


def installation_id(port):
    with urlopen(f"http://127.0.0.1:{port}/installation", timeout=2) as response:
        marker = response.read(33)
    if not re.fullmatch(b"[0-9a-f]{32}", marker):
        raise ValueError("service returned an invalid installation ID")
    return marker


def verdict(checker, port, flag, *, challenge_id=1, team_id=1, round_number=1):
    env = {**os.environ, "RSCTF_ACTION": "check", "RSCTF_TARGET_IP": "127.0.0.1",
           "RSCTF_TARGET_PORT": str(port), "RSCTF_CHALLENGE_ID": str(challenge_id),
           "RSCTF_TEAM_ID": str(team_id), "RSCTF_ROUND": str(round_number), "RSCTF_FLAG": flag}
    return subprocess.run([sys.executable, "-B", checker], env=env, timeout=8,
                          capture_output=True).returncode


class Rehearsal(unittest.TestCase):
    def test_round_rotation_and_patch_on_each_service(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generate(root / "event")
            for case in EXERCISES:
                with self.subTest(service=case.name):
                    pkg = root / "event/repository/challenges/AD/Web" / case.name
                    zips = root / "event/patches" / case.name
                    flag_file = root / "current-flag"
                    first, second = (f"flag{{{secrets.token_hex(16)}}}" for _ in range(2))
                    state_dir = root / case.name / "team-data"
                    state_dir.mkdir(parents=True)
                    installation = None
                    for version in ("starter", "patched", "patched-v2"):
                        src = root / case.name / version
                        with zipfile.ZipFile(zips / f"{version}.zip") as archive:
                            self.assertEqual(set(archive.namelist()), {"Dockerfile", "server.py", "exercise.py", ".rsctf-ssh.json"})
                            self.assertEqual(json.loads(archive.read(".rsctf-ssh.json")),
                                             [{"sourcePath": "exercise.py", "containerPath": "/app/exercise.py",
                                               "retainContent": True, "shareAfterClose": True}])
                            archive.extractall(src)
                        self.assertTrue((src / "Dockerfile").read_text().startswith("FROM rsctf-starter\n"))
                        flag_file.write_text(first)
                        with service(src, flag_file, state_dir) as port:
                            if installation is None:
                                installation = installation_id(port)
                            self.assertEqual(installation_id(port), installation)
                            checker = pkg / "checker/run.py"
                            self.assertEqual(verdict(checker, port, first), 0)
                            flag_file.write_text(second)
                            self.assertEqual(verdict(checker, port, first), 1)
                            self.assertEqual(verdict(checker, port, second), 0)
                            req = Request(f"http://127.0.0.1:{port}/evaluate", data=json.dumps(case.edge).encode())
                            with urlopen(req, timeout=2) as response:
                                self.assertEqual(json.load(response) == case.edge_result, version != "starter")
                            null_request = Request(f"http://127.0.0.1:{port}/evaluate", data=b"null")
                            if version == "patched":
                                with self.assertRaises(HTTPError) as rejected:
                                    urlopen(null_request, timeout=2)
                                self.assertEqual(rejected.exception.code, 400)
                                rejected.exception.close()
                            elif version == "patched-v2":
                                with urlopen(null_request, timeout=2) as response:
                                    self.assertEqual(json.load(response), case.null_result)
                        self.assertEqual(verdict(checker, port, second), 2)
                    for rollback in ("patched", "starter"):
                        with service(root / case.name / rollback, flag_file, state_dir) as port:
                            self.assertEqual(installation_id(port), installation)
                    fresh = root / case.name / "another-team"
                    fresh.mkdir()
                    with service(src, flag_file, fresh) as port:
                        self.assertNotEqual(installation_id(port), installation)


if __name__ == "__main__":
    unittest.main()
