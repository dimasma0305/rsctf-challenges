# rsctf challenge repository

This repository is a complete, safe-by-default example for rsctf's **Admin →
Repository Bindings** feature. Bind it and rsctf will find the root `.gzevent`,
create one hidden game, and import the seven nested challenge manifests.

The example is intentionally small and readable. Container manifests omit
`containerImage`, so Repository Bindings builds each adjacent `src/Dockerfile`
on the rsctf host during a trusted import. No prebuilt sample challenge image is
pulled from Docker Hub.

## What is imported

| Directory | Manifest type | What it demonstrates | Ready to enable? |
| --- | --- | --- | --- |
| `Jeopardy/Misc/static-handout` | `StaticAttachment` | One shared download and server-side static flag | Yes, after replacing the public demo flag |
| `Jeopardy/Misc/dynamic-handout` | `DynamicAttachment` | The current YAML shape and a multi-file attachment | **No** — see the current limitation below |
| `Jeopardy/Web/static-flag-service` | `StaticContainer` | One shared HTTP container with a static injected flag | Yes, after a runtime test and flag replacement |
| `Jeopardy/Web/dynamic-flag-service` | `DynamicContainer` | One HTTP container per team using `RSCTF_FLAG` | Yes, after a runtime test |
| `AD/Pwn/attack-defense-service` | `AttackDefense` | Platform-hosted per-team service, rotating flag file, and functional checker | Demo only; validate the entire A&D network first |
| `AD/Web/self-hosted-service` | `AttackDefense` | BYOC service image, outbound tunnel, rotating flag file, and functional checker | Demo only; validate the BYOC relay first |
| `Koth/Pwn/king-of-the-hill` | `KingOfTheHill` | Shared hill and `/koth/king` control marker | Demo only; Docker is currently required for reliable marker reads |

Repository imports always create challenges with `isEnabled = false`. This
event is also created with `hidden: true`, so importing it does not publish a
live competition. Trusted repository imports do mark the challenge review state
as active. During the scan, this example prepares three dependency-free A&D/KotH
checkers and builds the five container challenge images from their checked-in
source. Each checker pairs a reusable `lib.py` with a small decorated `run.py`.

New challenge authors should start with [`CONFIGURATION.md`](CONFIGURATION.md)
and [`CHECKERS.md`](CHECKERS.md). The active manifests are deliberately
commented as copyable templates, including both A&D hosting modes.

## Directory layout

```text
rsctf-challenges/
├── .gitignore
├── .gzevent
├── .github/workflows/validate.yml
├── AD/
│   ├── Pwn/attack-defense-service/{challenge.yaml,checker/,src/}
│   └── Web/self-hosted-service/{challenge.yaml,checker/,src/}
├── Koth/
│   └── Pwn/king-of-the-hill/{challenge.yaml,checker/,src/}
├── Jeopardy/
│   ├── Misc/{static-handout,dynamic-handout}/
│   └── Web/{static-flag-service,dynamic-flag-service}/
├── CHECKERS.md
├── CONFIGURATION.md
├── LICENSE.txt
├── scripts/{validate.mjs,test-checkers.py}
└── README.md
```

Every challenge is organized as `<mode>/<category>/<challenge>/`.

The scanner imports only event trees that contain an exact `.gzevent` filename.
A standalone `challenge.yaml` elsewhere in a repository is not imported by a
repository binding.

## Validate before pushing

From the repository root, run the package-free validator with Node.js:

```sh
node scripts/validate.mjs
```

It requires no `npm install`. The script fails on malformed/unknown manifest
keys, invalid mode/category directory placement, missing challenge types, unsafe
attachment paths, an unexpected `containerImage`, missing `src/Dockerfile`
build contexts, invalid ports/resources, or an unsupported checker layout. It
reports the current `DynamicAttachment` behavior as an expected limitation
rather than pretending that the example is playable.

Run the dependency-free checker smoke tests separately:

```sh
python3 scripts/test-checkers.py
```

They launch the bundled services on loopback and verify the `0` OK, `1` Mumble,
`2` Offline, and `3` InternalError exit-code contract.

## Import it from GitHub

1. Sign in as an administrator and open **Admin → Repository Bindings**. On the
   referenced deployment, that is
   [https://tcp.1pc.tf/admin/repo-bindings](https://tcp.1pc.tf/admin/repo-bindings).
2. Add `https://github.com/dimasma0305/rsctf-challenges.git`.
3. Choose `main`. This public repository needs no GitHub token.
4. For a private fork, use a fine-grained GitHub token with read-only
   repository contents access unless you intentionally need push-back.
5. Run **Scan now** and inspect the scan result. It should report one event and
   seven imported challenges.
6. Open the newly created hidden game and verify that all five container builds
   completed successfully. Set its real schedule, review every flag, build log,
   checker, and runtime, then enable only the challenges you tested.

The `.gzevent` deliberately omits `start` and `end`. On the first scan rsctf
defaults them to approximately tomorrow and 30 days from import. Set the real
times in the admin UI before unhiding the game. Event settings from `.gzevent`
are create-only; later scans preserve operator-edited game settings.

## What a rescan does

A rescan preserves the game row, but clears and recreates every challenge under
that event directory. Challenge IDs and challenge-level admin edits can change.
Do not use **Scan now** casually against a running event; treat Git as the source
of truth and test a rescan on a staging instance first.

## Attachment behavior

`provide` is relative to the directory containing `challenge.yaml`:

- A single file is attached as-is.
- A directory containing one file attaches that file as-is.
- A directory containing multiple files is packaged as a ZIP.
- If `provide` is omitted, rsctf looks for a `dist/` directory.
- Absolute paths, `..` traversal, and symlinks outside the package are rejected.

All files here are tiny text examples and contain no secrets.

## Container image behavior

The five container-based manifests intentionally omit `containerImage`. During
a trusted Repository Bindings scan, rsctf finds `src/Dockerfile`, stores the
complete challenge package as the immutable build source, selects `src/` as the
Docker context, generates an internal `rsctf/<game>/<challenge>:latest` tag, and
builds it through the configured Docker daemon. A concrete `containerImage`
would override this behavior and make the importer pull that registry image.

The Dockerfiles use the official `python:3.12-alpine` base only for Python's
standard-library HTTP server; all application behavior is included in each
`src/app.py`. Docker can still pull that base image while building if it is not
already cached. Mirror or replace the base image as well if the build host must
not access Docker Hub at all.

Before using these patterns in production:

- Pin the base image by digest or replace it with your reviewed internal base.
- Confirm rsctf uses the Docker challenge backend and can reach the daemon.
- In a split-role deployment, ensure every builder and container owner truly
  shares that daemon before setting `RSCTF_SHARED_DOCKER_DAEMON=true`.
- Inspect every import build log and resulting immutable image identity.
- Test resource limits and the exposed port through the player-visible route.

Persisted source builds are deliberately rejected on Kubernetes and on
independent node-local Docker daemons. Those deployments need reviewed images
in a registry accessible to every runtime node.

The static and dynamic services read the injected `RSCTF_FLAG` environment
variable. That is the current rsctf contract for normal container challenges.

## A&D checker contract

Both A&D examples include a standard-library-only checker directory. Its
`lib.py` provides `AdContext`, verdict exceptions, bounded HTTP helpers, and the
`@ad_checker` decorator; `run.py` contains only the service-specific assertions
and decorated entry point. Copy both files when using the template. rsctf
delivers the rotating flag to the service first, then gives the checker the same
expected value as `RSCTF_FLAG`. The checker retrieves and compares it through
player-visible behavior without changing service state.

The platform-hosted service reads its writable `RSCTF_FLAG_FILE` inside the
managed container. The self-hosted service reads `/shared/flag`, which the BYOC
agent updates through the outbound tunnel. The checker-facing target contract is
the same in both modes.

See [`CHECKERS.md`](CHECKERS.md) for environment variables, the `0` OK / `1`
Mumble / `2` Offline / `3` InternalError mapping, sandbox constraints, and local
commands.

A&D additionally requires the rsctf A&D network/VPN, accepted teams, round
scheduler, container backend, and checker sandbox to be working. Keep the demo
disabled until a full two-team staging run passes.

## King of the Hill contract

The hill accepts a team's current control token at
`/claim?token=URL_ENCODED_TOKEN` and atomically writes it to `/koth/king`. rsctf
executes into the shared hill container, reads that marker, and maps the exact
token to its team. Its custom checker uses `KothContext` and `@koth_checker` to
verify `/health` without requiring `RSCTF_FLAG` or touching the ownership
marker. This also satisfies the official scoring-start requirement that every
enabled engine challenge has a prepared checker.

Current Kubernetes support cannot reliably provide every Docker-style KotH exec
and networking behavior. Use the Docker backend for this sample unless your
cluster-specific implementation has been tested end to end.

## Current DynamicAttachment limitation

The manifest is included because `DynamicAttachment` is a current enum and must
be represented in a complete repository example. However, the current repository
importer stores `provide` as one challenge-owned attachment and imports `flags`
as unassigned flag rows. Participation provisioning creates a `GameInstance`
without assigning one of those flag/attachment rows. The player path therefore
does not yet produce a distinct per-team download/flag that can be graded.

Keep `Dynamic Attachment (illustrative)` disabled. Use `StaticAttachment` when
all teams may receive the same file, or implement/test the missing per-team asset
generation and flag assignment before enabling a dynamic attachment challenge.

## Public demo values are not secrets

Every literal flag in this directory is visible in Git. That is deliberate for
documentation, but it makes those values unsuitable for a real event. Replace
them, review the resulting Git history, and rotate any value that has ever been
published before enabling a challenge.
