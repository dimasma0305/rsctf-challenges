# rsctf challenge repository agent entry point

This repository is a copyable rsctf Repository Bindings example. Keep it easy for a
first-time challenge author to navigate, preserve the importer contracts demonstrated
by the fixtures, and keep human documentation centralized under `docs/`.

## Mandatory workflow

For challenge creation, manifest changes, source/checker work, playtesting, review,
or repository restructuring, read
`.agents/skills/rsctf-challenge-authoring/SKILL.md` completely. Follow its routing
table and read every reference it selects before editing.

Human-facing details are authoritative under `docs/`. Do not create scattered
author notes or component READMEs inside `challenges/`; improve the relevant page in
`docs/` instead. Player-issued files inside a challenge's `dist/` directory are not
author documentation and remain beside the manifest.

## Repository contract

- Keep the single event manifest at `.gzevent` and start examples with `hidden: true`.
- Put packages at `challenges/<mode>/<category>/<slug>/challenge.yaml`, where mode is
  `AD`, `Jeopardy`, or `Koth` and category matches the manifest.
- Keep default scoring fields absent from example manifests so rsctf remains the
  source of truth. Add `minScoreRate`, `difficulty`, or `submissionLimit` only for a
  deliberate Jeopardy override; never add them to A&D or KotH.
- Keep container build input in the package's `src/` directory. Omit
  `containerImage` when demonstrating trusted Repository Bindings source builds.
- Do not hand-edit container matrices. Direct package `src/Dockerfile` and
  `generator/Dockerfile` paths are discovered by `scripts/container-images.py`.
  Every service's normalized mode/category/slug tag needs a functional case in
  `scripts/test-container-images.py`; discovery must fail when coverage is missing.
- Keep GitHub manifest validation on rsctf's own `rsctf challenge check` command.
  Import the maintained `dimasma0305/rsctf` action; do not copy a platform-validator
  wrapper into this repository or replace it with the local JavaScript convention
  validator.
- Keep A&D/KotH checker transport and assertions in `checker/run.py`; keep the shared
  platform runner in `checker/lib.py`. Copy a complete checker directory.
- Keep deterministic generator code in `generator/` beside its manifest.
- Never place a real flag, organizer token, observer secret, admin JWT, production
  hostname, or private writeup in committed examples, screenshots, logs, or fixtures.
- Treat all committed demo flags as disclosed. Changing the current file does not
  remove a value from Git history.
- Do not claim that `DynamicAttachment` is playable until rsctf assigns distinct
  per-participation handouts and flags; the included package is schema-only.

## Player boundary

A playtest must match the real delivery mode: service only, handout only, or hybrid.
Do not give a black-box player repository source, the intended solution, a known-good
solver, container administration, build logs, or inherited author/agent context.
`playtest/` is gitignored convenience space, not a sandbox; enforce isolation in the
runner or use a separate workspace/account.

Screenshots must come from the player-visible route, identity, and build they claim to
show. Prefer text logs for text protocols. Redact flags and unrelated secrets, and do
not use mocked browser states or hand-written terminal output as evidence.

## Completion gate

Run focused checks while editing, then from the repository root run:

```sh
make test
make validate-platform
make test-container-images
```

Set `RSCTF` to the matching official binary when it is not on `PATH`.
Container lifecycle checks are required when `src/`, a Dockerfile, or `generator/` changes.
Documentation-only work may skip Docker builds, but link and command examples must
still be checked. Import/release work is incomplete until the hidden staging scan,
normal-player smoke test, and applicable multi-team A&D/KotH rehearsal pass.
