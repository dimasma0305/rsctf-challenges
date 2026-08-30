# rsctf challenge repository agent entry point

This repository is a copyable rsctf Repository Bindings example. Keep it easy for a
first-time challenge author to navigate, preserve the importer contracts demonstrated
by the fixtures, and keep human documentation centralized under `docs/`.

## Automatic skill routing

When Codex is launched from this repository root or a descendant, the repository-local
skills under `.agents/skills/` allow implicit invocation. Select the smallest matching
workflow from its description, read that `SKILL.md` completely, and read every reference it
routes before acting:

| Task | Skill |
| --- | --- |
| brainstorm an exploit, clue path, or difficulty target | `$rsctf-challenge-design` |
| create or edit manifests, source, handouts, checkers, generators, or observers | `$rsctf-challenge-authoring` |
| write/reproduce the organizer README.md or solve.py | `$rsctf-challenge-solution` |
| prepare and run a fresh blind solve | `$rsctf-challenge-playtest` |
| assess a completed blind report and unintended paths | `$rsctf-playtest-review` |
| decide whether a revision is ready to import or enable | `$rsctf-challenge-release-review` |

A request spanning the full lifecycle uses those skills in that order where applicable. Do
not use the authoring context as the blind solver. Explicit `$skill-name` invocation remains
available when the user wants to force one workflow; otherwise matching requests should
select it automatically.

Human-facing details are authoritative under `docs/`. Do not create scattered
author notes or component READMEs inside `challenges/`; improve the relevant page in
`docs/` instead. Player-issued files inside a challenge's `dist/` directory are not
author documentation and remain beside the manifest. Every package has tracked organizer-only
`solution/README.md` and `solution/solve.py` files. Read `docs/solutions.md` before handling
them and never expose them to a blind solver.

## Repository contract

- Keep the single event manifest at `.gzevent` and start examples with `hidden: true`.
- Put packages at `challenges/<mode>/<category>/<slug>/challenge.yaml`, where mode is
  `AD`, `Jeopardy`, or `Koth` and category matches the manifest.
- Follow `docs/authoring-contract.md` for canonical file ownership. Delete unused package
  components and do not add generic directories or duplicate files without a real owner.
- Keep default scoring fields absent from example manifests so rsctf remains the
  source of truth. Add `minScoreRate`, `difficulty`, or `submissionLimit` only for a
  deliberate Jeopardy override; never add them to A&D or KotH.
- Keep container build input in the package's `src/` directory. Omit
  `containerImage` when demonstrating trusted Repository Bindings source builds.
- Do not hand-edit container matrices. Direct package `src/Dockerfile` and
  `generator/Dockerfile` paths are discovered by `rsctf challenge matrix`. Every
  long-running service image must declare a meaningful Docker `HEALTHCHECK`; CI
  builds the dynamic matrix and fails unless each service becomes healthy.
- Keep GitHub manifest validation on rsctf's own `rsctf challenge check` command.
  Import the maintained `dimasma0305/rsctf` action; do not copy a platform-validator
  wrapper, discovery helper, or repository-local checker into this repository.
- Keep A&D/KotH checker transport and assertions in `checker/run.py`; keep the shared
  platform runner in `checker/lib.py`. Copy a complete checker directory.
- Keep deterministic generator code in `generator/` beside its manifest.
- Never place a real flag, organizer token, observer secret, admin JWT, production hostname,
  or unredacted live-secret evidence in committed solutions, screenshots, logs, or fixtures.
- Require `solution/README.md` and a small `solution/solve.py` in every package. Keep both out
  of `dist/`, `src/`, generators, observer bundles, and playtest rooms. Never place a
  challenge/event manifest inside `solution/` because rsctf discovers manifests independently
  of Git ignore rules.
- Treat all committed demo flags as disclosed. Changing the current file does not
  remove a value from Git history.
- Do not claim that `DynamicAttachment` is playable until rsctf assigns distinct
  per-participation handouts and flags; the included package is schema-only.

## Player boundary

A playtest must match the real delivery mode: managed service, handout, hybrid, or
self-hosted BYOC. Do not give a player repository source, the intended solution, a
known-good solver, build logs, organizer-side container administration, or inherited
author/agent context unless that material is part of the real player delivery. A BYOC
player receives the exact setup bundle and image and may control only the team-owned
host and containers that the real event permits.
The ignored `.agents/skills/rsctf-challenge-playtest/playtest/` room is convenience space,
not a sandbox; enforce isolation in the runner or use a separate workspace/account.

Screenshots must come from the player-visible route, identity, and build they claim to
show. Prefer text logs for text protocols. Redact flags and unrelated secrets, and do
not use mocked browser states or hand-written terminal output as evidence.

## Completion gate

Run focused checks while editing, then from the repository root run:

```sh
make validate
make matrix
```

Set `RSCTF` to the matching official binary when it is not on `PATH`.
When `src/`, a Dockerfile, or `generator/` changes, require the dynamic GitHub
container job (or an equivalent local build) to pass. Docker health proves service
availability, not checker correctness or solvability; verify those through the
player-equivalent and hidden-staging gates below.
Documentation-only work may skip Docker builds, but link and command examples must
still be checked. Import/release work is incomplete until the hidden staging scan,
normal-player smoke test, and applicable multi-team A&D/KotH rehearsal pass.
