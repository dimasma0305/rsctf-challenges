# rsctf challenge repository

This repository is a complete, safe-by-default example for rsctf's **Admin →
Repository Bindings** feature. Bind it and rsctf will find the root `.gzevent`,
create one hidden game, and import the nine nested challenge manifests.

The example is intentionally small and readable. Container manifests omit
`containerImage`, so Repository Bindings builds each adjacent `src/Dockerfile`
on the rsctf host during a trusted import. No prebuilt sample challenge image is
pulled from Docker Hub.

## What is imported

| Directory | Manifest type | What it demonstrates | Ready to enable? |
| --- | --- | --- | --- |
| `Jeopardy/Misc/static-handout` | `StaticAttachment` | One shared download and server-side static flag | Yes, after replacing the public demo flag |
| `Jeopardy/Misc/dynamic-handout` | `DynamicAttachment` | The current YAML shape and a multi-file attachment | **No** — see the current limitation below |
| `Jeopardy/Misc/deterministic-variant` | `StaticAttachment` + provenance | An auto-built deterministic generator derives a different challenge statement and flag for each participation | Demo only; configure the platform key and generate before the event |
| `Jeopardy/Web/static-flag-service` | `StaticContainer` | One shared HTTP container with a static injected flag | Yes, after a runtime test and flag replacement |
| `Jeopardy/Web/dynamic-flag-service` | `DynamicContainer` | One HTTP container per team using `RSCTF_FLAG` | Yes, after a runtime test |
| `AD/Pwn/attack-defense-service` | `AttackDefense` | Platform-hosted raw TCP line service, rotating flag file, and pwntools checker | Demo only; validate the entire A&D network first |
| `AD/Web/self-hosted-service` | `AttackDefense` | BYOC HTTP service, outbound tunnel, rotating flag file, and HTTP checker | Demo only; validate the BYOC relay first |
| `Koth/Pwn/king-of-the-hill` | `KingOfTheHill` | Shared hill and `/koth/king` control marker | Demo only; Docker is currently required for reliable marker reads |
| `Koth/Web/api-observed-hill` | `KingOfTheHill` | Multi-team proof arena plus an independently hosted signed referee | Demo only; configure and protect the one-time referee secret |

Repository imports always create challenges with `isEnabled = false`. This
event is also created with `hidden: true`, so importing it does not publish a
live competition. Trusted repository imports do mark the challenge review state
as active. During the scan, this example prepares four A&D/KotH checkers and
builds the six service images from their checked-in source. It also builds and
contract-tests the provenance `generator/Dockerfile`, storing the resolved
immutable image ID internally. rsctf runs that generator again only when an
administrator generates participation variants. Each
checker pairs a protocol-neutral `lib.py` with registered checks in `run.py`;
the two A&D checkers additionally install exact `pwntools==4.15.0` and
`httpx==0.28.1` wheel requirements.

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
│   ├── Pwn/king-of-the-hill/{challenge.yaml,checker/,src/}
│   └── Web/api-observed-hill/{challenge.yaml,checker/,observer/,src/}
├── Jeopardy/
│   ├── Misc/{static-handout,dynamic-handout,deterministic-variant}/
│   └── Web/{static-flag-service,dynamic-flag-service}/
├── CHECKERS.md
├── CONFIGURATION.md
├── LICENSE.txt
├── PROVENANCE.md
├── scripts/{validate.mjs,test-provenance.py,generate-variants.mjs,issue-solve-receipt.mjs,...}
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
build contexts, invalid ports/resources, an unsupported checker layout, or a
missing `generator/Dockerfile` or mutable/mismatched fallback generator
reference. It
reports the current `DynamicAttachment` behavior as an expected limitation
rather than pretending that the example is playable.

Exercise the deterministic generator contract locally:

```sh
python3 scripts/test-provenance.py
node scripts/test-provenance-automation.mjs
```

The first test runs the generator twice with the same input, verifies
byte-identical output, then changes the seed and verifies that the derived
instance changes. The second exercises both API clients against a local mock
control surface and checks their routes, credentials, request bodies, and
responses.

Run the checker smoke tests separately after installing the A&D checkers'
pinned wheel dependencies as described in [`CHECKERS.md`](CHECKERS.md):

```sh
/tmp/rsctf-example-checkers/bin/python scripts/test-checkers.py
```

They launch the bundled services on loopback and verify the `0` OK, `1` Mumble,
`2` Offline, and `3` InternalError exit-code contract.

Exercise the Leaderboard referee separately:

```sh
python3 scripts/test-koth-observer.py
```

It verifies exact HMAC signing, per-round context fencing, capability-hash
filtering, explicit zero snapshots, normalization inputs, persistent restart,
feed-gap failure, and deduplication without requiring a live RSCTF deployment.

## Import it from GitHub

1. Sign in as an administrator and open **Admin → Repository Bindings**. On the
   referenced deployment, that is
   [https://tcp.1pc.tf/admin/repo-bindings](https://tcp.1pc.tf/admin/repo-bindings).
2. Add `https://github.com/dimasma0305/rsctf-challenges.git`.
3. Choose `main`. This public repository needs no GitHub token.
4. For a private fork, use a fine-grained GitHub token with read-only
   repository contents access unless you intentionally need push-back.
5. Run **Scan now** and inspect the scan result. It should report one event and
   nine imported challenges.
6. Open the newly created hidden game and verify that all six container builds
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

The six container-based manifests intentionally omit `containerImage`. During
a trusted Repository Bindings scan, rsctf finds `src/Dockerfile`, stores the
complete challenge package as the immutable build source, selects `src/` as the
Docker context, generates an internal `rsctf/<game>/<challenge>:latest` tag, and
builds it through the configured Docker daemon. A concrete `containerImage`
would override this behavior and make the importer pull that registry image.

The Dockerfiles use the official `python:3.12-alpine` base only for small
Python standard-library services; all application behavior is included in each
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

## Challenge provenance automation

[`Jeopardy/Misc/deterministic-variant/challenge.yaml`](Jeopardy/Misc/deterministic-variant/challenge.yaml)
shows the repository-facing policy. It tells rsctf which immutable generator
mode is requested and that variants are scoped per participation. Repository
Bindings automatically archives, builds, and deterministic-replay checks the
adjacent `generator/Dockerfile`, then stores its immutable identity internally.

After import, configure `RSCTF_EVENT_VPN_CREDENTIAL_KEY`, accept the teams, and
run the pre-event generation endpoint with
[`scripts/generate-variants.mjs`](scripts/generate-variants.mjs). Players still
submit only a flag. If a challenge needs an external verifier, set
`solveReceiptMode` to `Optional` or `Required`, configure its identity, and
have that verifier call the
control-only receipt endpoint through
[`scripts/issue-solve-receipt.mjs`](scripts/issue-solve-receipt.mjs); players
then submit the signed proof returned by rsctf. They never upload an exploit or
a solver to the platform.

See [`PROVENANCE.md`](PROVENANCE.md) for the exact generator input/output,
automatic-build behavior, registry fallback, environment variables, API calls,
trust boundaries, and safe retry behavior.

## A&D checker contract

Both A&D examples keep platform concerns in `lib.py`: `AdContext`, verdict
exceptions, `@checker`, and `run_ad_checker()`. `run.py` implements the
service's actual protocol and registers a suite of focused checks. The runner
cryptographically shuffles their order for each process invocation and attempts
every registered function once. It continues after individual failures and
combines them as InternalError, Offline, Mumble, then OK.
The managed Pwn demo uses `pwntools==4.15.0` for its newline-framed raw TCP
protocol; the self-hosted Web demo uses `httpx==0.28.1` for HTTP. A binary or
custom TCP challenge can replace that code in `run.py` without changing the
platform helper. Copy the complete checker directory, including any
`requirements.txt`. rsctf delivers the rotating flag to the service first, then
gives the checker the same expected value as `RSCTF_FLAG`. The checker retrieves
and compares it through player-visible behavior without changing service state.

The complete A&D suite covers both service health and the current flag. Focused
checks may cover one responsibility each, but they must be read-only and cannot
depend on registration or execution order. Varying request order is
defense-in-depth against checker fingerprinting, but it does not hide the
platform's source IP and cannot by itself prevent a service from source-IP
allowlisting the checker. The legacy one-function `@ad_checker` entry point
remains supported.

The platform-hosted service reads its writable `RSCTF_FLAG_FILE` inside the
managed container. The self-hosted service reads `/shared/flag`, which the BYOC
agent updates through the outbound tunnel. Both checker modes receive the same
platform context, while each challenge's `run.py` defines its own application
protocol.

See [`CHECKERS.md`](CHECKERS.md) for environment variables, the `0` OK / `1`
Mumble / `2` Offline / `3` InternalError mapping, sandbox constraints, and local
commands.

A&D additionally requires the RSCTF A&D network/VPN, accepted teams, round
scheduler, container backend, and checker sandbox to be working. Keep the demo
disabled until a full two-team staging run passes.

## King of the Hill contracts

The marker example accepts a team's current control token at
`/claim?token=URL_ENCODED_TOKEN` and atomically writes it to `/koth/king`. RSCTF
executes into the shared hill container, reads that marker, and maps the exact
token to its team. Current Kubernetes support cannot reliably provide every
Docker-style exec and networking behavior, so use the Docker backend for that
sample unless your cluster implementation has been tested end to end.

The Leaderboard example accepts each team's current capability only to start a
short-lived, one-use proof session and immediately reduces it to a SHA-256
hash. A separately deployed referee drains the ordered evidence feed, filters
it against the current eligible hashes from RSCTF, and signs bounded activity
and ordered objective ratios for every active team. It never submits points or
raw capabilities. RSCTF independently normalizes the native budgets, writes an
explicit zero for an omitted team, assigns exact tied-leader credit, and scores
only a snapshot that remains unchanged around a healthy functional check. The
HMAC secret is never placed in the arena image. This makes the evidence input
portable to Kubernetes and private workers, provided the referee has stable
routes to RSCTF and the active arena. Follow
[`Koth/Web/api-observed-hill/observer/README.md`](Koth/Web/api-observed-hill/observer/README.md)
before enabling it.

Neither input mode is a score webhook. RSCTF runs the functional checker,
requires stable healthy observations, owns crown cycles, and applies the fixed
KotH formula. Both examples use `KothContext`, `@checker`, and
`run_koth_checker()` without `RSCTF_FLAG`; the checker never reads or changes
controller state. The legacy `@koth_checker` entry point remains supported.
Preparing a checker also satisfies the official scoring-start requirement for
each enabled engine challenge.

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
