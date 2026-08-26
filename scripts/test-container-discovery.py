#!/usr/bin/env python3
"""Regression tests for dynamic container matrix discovery."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("container-images.py")


def add_context(root: Path, relative: str) -> None:
    context = root / relative
    context.mkdir(parents=True)
    (context / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (context.parent / "challenge.yaml").write_text(
        "name: Matrix fixture\ntype: StaticContainer\n", encoding="utf-8"
    )


def invoke(root: Path, command: str = "matrix") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, "--root", str(root)],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )


def add_smoke_runner(root: Path, cases: list[str]) -> None:
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "test-container-images.py").write_text(
        "import json\nprint(json.dumps(" + repr(cases) + "))\n",
        encoding="utf-8",
    )


class ContainerDiscoveryTests(unittest.TestCase):
    def test_catalog_has_functional_coverage_for_every_service(self) -> None:
        result = invoke(SCRIPT.parent.parent, "check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("every service has a functional smoke handler", result.stdout)

    def test_matrix_discovers_services_and_generators_in_stable_order(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rsctf-matrix-") as directory:
            root = Path(directory)
            (root / "challenges").mkdir()
            add_context(root, "challenges/Jeopardy/Web/zeta-service/src")
            add_context(root, "challenges/Jeopardy/Misc/alpha-variant/generator")

            result = invoke(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout),
                {
                    "include": [
                        {
                            "context": "challenges/Jeopardy/Misc/alpha-variant/generator",
                            "name": "Jeopardy/Misc/alpha-variant (generator)",
                            "smoke": "",
                            "tag": "jeopardy-misc-alpha-variant-generator",
                        },
                        {
                            "context": "challenges/Jeopardy/Web/zeta-service/src",
                            "name": "Jeopardy/Web/zeta-service",
                            "smoke": "jeopardy-web-zeta-service",
                            "tag": "jeopardy-web-zeta-service",
                        },
                    ]
                },
            )

            github = invoke(root, "github-output")
            self.assertEqual(github.returncode, 0, github.stderr)
            outputs = dict(line.split("=", 1) for line in github.stdout.splitlines())
            self.assertEqual(outputs["count"], "2")
            self.assertEqual(json.loads(outputs["matrix"]), json.loads(result.stdout))

    def test_tag_collisions_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rsctf-matrix-") as directory:
            root = Path(directory)
            (root / "challenges").mkdir()
            add_context(root, "challenges/AD/Pwn/Collision-Name/src")
            add_context(root, "challenges/AD/Pwn/collision-name/src")

            result = invoke(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Docker tag collision", result.stderr)

    def test_symlinked_dockerfile_fails_closed(self) -> None:
        if not hasattr(Path, "symlink_to"):
            self.skipTest("symlinks are unavailable")
        with tempfile.TemporaryDirectory(prefix="rsctf-matrix-") as directory:
            root = Path(directory)
            context = root / "challenges/AD/Pwn/symlink-service/src"
            context.mkdir(parents=True)
            (context.parent / "challenge.yaml").write_text(
                "name: Symlink fixture\ntype: AttackDefense\n", encoding="utf-8"
            )
            outside = root / "outside.Dockerfile"
            outside.write_text("FROM scratch\n", encoding="utf-8")
            (context / "Dockerfile").symlink_to(outside)

            result = invoke(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("must be a regular file, not a symlink", result.stderr)

    def test_missing_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rsctf-matrix-") as directory:
            root = Path(directory)
            context = root / "challenges/Koth/Web/missing-manifest/src"
            context.mkdir(parents=True)
            (context / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

            result = invoke(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("challenge manifest", result.stderr)

    def test_missing_functional_smoke_handler_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rsctf-matrix-") as directory:
            root = Path(directory)
            (root / "challenges").mkdir()
            add_context(root, "challenges/Jeopardy/Web/new-service/src")
            add_smoke_runner(root, [])

            result = invoke(root, "check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("jeopardy-web-new-service", result.stderr)


if __name__ == "__main__":
    unittest.main()
