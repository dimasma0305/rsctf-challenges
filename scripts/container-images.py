#!/usr/bin/env python3
"""Discover and exercise every repository-owned container build context."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
COMPONENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TAG_PATTERN = re.compile(r"[^a-z0-9_.-]+")
TAG_VALUE_PATTERN = re.compile(r"^[a-z0-9_][a-z0-9_.-]{0,127}$")


class DiscoveryError(RuntimeError):
    """A build context cannot be represented safely in the CI matrix."""


@dataclass(frozen=True)
class ImageSpec:
    name: str
    context: str
    tag: str
    smoke: str

    def github_entry(self) -> dict[str, str]:
        return {
            "name": self.name,
            "context": self.context,
            "tag": self.tag,
            "smoke": self.smoke,
        }

    def image(self, prefix: str, suffix: str) -> str:
        return f"{prefix}/{self.tag}:{suffix}"


def require_real_directory(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise DiscoveryError(f"cannot inspect {label} {path}: {error}") from error
    if not stat.S_ISDIR(metadata.st_mode):
        raise DiscoveryError(f"{label} must be a real directory: {path}")


def require_real_file(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise DiscoveryError(f"cannot inspect {label} {path}: {error}") from error
    if not stat.S_ISREG(metadata.st_mode):
        raise DiscoveryError(f"{label} must be a regular file, not a symlink: {path}")


def require_real_ancestors(root: Path, path: Path) -> None:
    relative = path.relative_to(root)
    current = root
    for component in relative.parts:
        current /= component
        require_real_directory(current, "build path component")


def image_tag(parts: tuple[str, ...], kind: str) -> str:
    tag_parts = (*parts, "generator") if kind == "generator" else parts
    raw = "-".join(tag_parts)
    value = TAG_PATTERN.sub("-", raw.lower()).strip("-.")
    if not TAG_VALUE_PATTERN.fullmatch(value):
        raise DiscoveryError(f"build path does not produce a safe Docker tag: {raw!r}")
    return value


def discover(root: Path) -> list[ImageSpec]:
    root = root.resolve()
    challenges = root / "challenges"
    require_real_directory(challenges, "challenges root")

    dockerfiles: list[Path] = []
    for kind in ("src", "generator"):
        dockerfiles.extend(challenges.glob(f"*/*/*/{kind}/Dockerfile"))

    specs: list[ImageSpec] = []
    tags: dict[str, str] = {}
    for dockerfile in sorted(dockerfiles, key=lambda path: path.as_posix()):
        context = dockerfile.parent
        package = context.parent
        relative_package = package.relative_to(challenges)
        parts = relative_package.parts
        if len(parts) != 3 or any(not COMPONENT_PATTERN.fullmatch(part) for part in parts):
            raise DiscoveryError(
                "container packages must use challenges/<mode>/<category>/<slug>: "
                f"{relative_package.as_posix()}"
            )

        require_real_ancestors(root, context)
        require_real_file(dockerfile, "Dockerfile")
        require_real_file(package / "challenge.yaml", "challenge manifest")

        kind = context.name
        tag = image_tag(parts, kind)
        context_name = context.relative_to(root).as_posix()
        if previous := tags.get(tag):
            raise DiscoveryError(
                f"Docker tag collision {tag!r} between {previous} and {context_name}"
            )
        tags[tag] = context_name

        package_name = relative_package.as_posix()
        specs.append(
            ImageSpec(
                name=(
                    package_name
                    if kind == "src"
                    else f"{package_name} (generator)"
                ),
                context=context_name,
                tag=tag,
                smoke=tag if kind == "src" else "",
            )
        )
    return specs


def matrix(specs: list[ImageSpec]) -> str:
    payload = {"include": [spec.github_entry() for spec in specs]}
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def parse_docker_command(value: str) -> list[str]:
    command = shlex.split(value)
    if not command:
        raise DiscoveryError("--docker must name a Docker-compatible command")
    return command


def validate_image_component(value: str, option: str) -> str:
    if not value or any(character.isspace() for character in value):
        raise DiscoveryError(f"{option} must be one non-empty value without whitespace")
    return value


def build_images(
    root: Path,
    specs: list[ImageSpec],
    docker: list[str],
    prefix: str,
    suffix: str,
) -> None:
    for spec in specs:
        image = spec.image(prefix, suffix)
        print(f"Building {spec.context} as {image}", flush=True)
        subprocess.run(
            [*docker, "build", "--tag", image, spec.context],
            cwd=root,
            check=True,
        )


def smoke_images(root: Path, specs: list[ImageSpec], prefix: str, suffix: str) -> None:
    runner = root / "scripts" / "test-container-images.py"
    require_real_file(runner, "container smoke runner")
    for spec in specs:
        if not spec.smoke:
            continue
        subprocess.run(
            [
                sys.executable,
                os.fspath(runner),
                "--image",
                spec.image(prefix, suffix),
                "--case",
                spec.smoke,
            ],
            cwd=root,
            check=True,
        )


def validate_smoke_coverage(root: Path, specs: list[ImageSpec]) -> None:
    runner = root / "scripts" / "test-container-images.py"
    require_real_file(runner, "container smoke runner")
    result = subprocess.run(
        [sys.executable, os.fspath(runner), "--list-cases"],
        cwd=root,
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    try:
        cases = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise DiscoveryError("container smoke runner returned invalid case JSON") from error
    if not isinstance(cases, list) or any(not isinstance(case, str) for case in cases):
        raise DiscoveryError("container smoke runner case list must be a JSON string array")
    required = {spec.smoke for spec in specs if spec.smoke}
    missing = sorted(required.difference(cases))
    if missing:
        raise DiscoveryError(
            "service build contexts need functional handlers in "
            f"scripts/test-container-images.py: {', '.join(missing)}"
        )


def add_root_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)


def add_build_arguments(parser: argparse.ArgumentParser) -> None:
    add_root_argument(parser)
    parser.add_argument("--docker", default=os.environ.get("DOCKER", "docker"))
    parser.add_argument("--image-prefix", default="rsctf-example")
    parser.add_argument("--tag-suffix", default="local")


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    matrix_parser = commands.add_parser("matrix", help="print a GitHub matrix as JSON")
    add_root_argument(matrix_parser)
    github_parser = commands.add_parser(
        "github-output", help="print matrix and count lines for GITHUB_OUTPUT"
    )
    add_root_argument(github_parser)
    check_parser = commands.add_parser(
        "check", help="verify every discovered service has a functional smoke handler"
    )
    add_root_argument(check_parser)
    build_parser = commands.add_parser("build", help="build every discovered image")
    add_build_arguments(build_parser)
    test_parser = commands.add_parser(
        "test", help="build all images and functionally smoke every service"
    )
    add_build_arguments(test_parser)

    arguments = parser.parse_args()
    try:
        root = arguments.root.resolve()
        specs = discover(root)
        if arguments.command == "matrix":
            print(matrix(specs))
        elif arguments.command == "github-output":
            print(f"matrix={matrix(specs)}")
            print(f"count={len(specs)}")
        elif arguments.command == "check":
            validate_smoke_coverage(root, specs)
            print(
                f"OK: discovered {len(specs)} container build contexts; "
                "every service has a functional smoke handler."
            )
        else:
            prefix = validate_image_component(arguments.image_prefix, "--image-prefix")
            suffix = validate_image_component(arguments.tag_suffix, "--tag-suffix")
            docker = parse_docker_command(arguments.docker)
            if arguments.command == "test":
                validate_smoke_coverage(root, specs)
            build_images(root, specs, docker, prefix, suffix)
            if arguments.command == "test":
                smoke_images(root, specs, prefix, suffix)
    except (DiscoveryError, OSError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
