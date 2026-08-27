# Getting started

This repository demonstrates one hidden event and every current rsctf challenge
type. Start by copying the closest working package; do not assemble a manifest from
memory. Read the [challenge authoring contract](authoring-contract.md) before adding a
new directory; it defines the complete package layout, file ownership, and release
lifecycle.

For an AI-assisted end-to-end workflow, start with `$rsctf-challenge-design`, implement
with `$rsctf-challenge-authoring`, prove the intended solve with
`$rsctf-challenge-solution`, run a fresh blind solve with
`$rsctf-challenge-playtest`, review it with `$rsctf-playtest-review`, and finish with
`$rsctf-challenge-release-review`. The repository selects these skills implicitly when a
request clearly matches one phase.

## Prerequisites

- Python 3.12 or newer when developing the included services, generators, observers,
  or checkers.
- Docker when building or locally running container challenges.
- The `rsctf` binary from the matching release for local importer-owned schema and
  semantic validation and container discovery. GitHub Actions obtains it through the
  reusable rsctf action.

Run `make help` at any time to see the supported commands.

## Choose an example

| Type or hosting mode | Copy this directory | Important caveat |
| --- | --- | --- |
| shared static handout | `challenges/Jeopardy/Misc/static-handout` | replace the public demo flag |
| per-participation deterministic variant | `challenges/Jeopardy/Misc/deterministic-variant` | configure the event key and freeze variants before start |
| dynamic handout schema | `challenges/Jeopardy/Misc/dynamic-handout` | illustrative only; current per-team assignment is incomplete |
| shared static container | `challenges/Jeopardy/Web/static-flag-service` | replace the public demo flag and runtime-test it |
| per-team dynamic container | `challenges/Jeopardy/Web/dynamic-flag-service` | reads the injected `RSCTF_FLAG` |
| platform-hosted A&D | `challenges/AD/Pwn/attack-defense-service` | rehearse the full A&D network with two teams |
| self-hosted/BYOC A&D | `challenges/AD/Web/self-hosted-service` | rehearse the relay and flag delivery |
| marker KotH | `challenges/Koth/Pwn/king-of-the-hill` | use a tested Docker backend for marker reads |
| signed-API Leaderboard KotH | `challenges/Koth/Web/api-observed-hill` | deploy and protect the independent referee |

## Create the package

The layout is always:

```text
challenges/<mode>/<category>/<slug>/
├── challenge.yaml       # rsctf import contract
├── dist/                # exact player handout, when applicable
├── src/                 # trusted local container build context, when applicable
├── checker/             # A&D/KotH functional checker, when applicable
├── generator/           # deterministic variant generator, when applicable
├── observer/            # organizer-run referee, when applicable
└── solution/            # required tracked organizer material
    ├── README.md        # concise writeup
    └── solve.py         # simple reference solver
```

`challenge.yaml`, `solution/README.md`, and `solution/solve.py` are universal. Delete every
other optional component the challenge does not use. The component matrix and audience
boundary are defined in the [authoring contract](authoring-contract.md).

For example:

```sh
cp -R \
  challenges/Jeopardy/Web/dynamic-flag-service \
  challenges/Jeopardy/Web/my-service
```

Then make these edits:

1. Change the directory slug and the manifest's `name`, `author`, description,
   category, and only the fields required by this challenge type. Leave
   `minScoreRate`, `difficulty`, and `submissionLimit` absent to inherit rsctf's
   defaults; add them only for a deliberate event-specific override.
2. Replace the demo service or handout. Delete copied components the challenge does
   not use; do not keep placeholder code.
3. Replace every demo flag. For dynamic services, keep the injected flag contract
   instead of hard-coding a value.
4. Adapt `checker/run.py` to the real player-visible protocol. Keep checker requests
   bounded, read-only, and independent of execution order.
5. Update the relevant page under `docs/` if the new package demonstrates a contract
   teammates need to understand.

The copied package already contains a working solution example. Replace it as soon as the new
design becomes testable:

```sh
cp docs/templates/solution.md \
  challenges/Jeopardy/Web/my-service/solution/README.md
cp docs/templates/solve.py \
  challenges/Jeopardy/Web/my-service/solution/solve.py
```

Follow [Solutions and reference solvers](solutions.md). Keep a real pre-event repository
restricted because anyone with Git read access can read these tracked organizer files.

The category must be one supported by the importer and must match the middle path
component. See the [manifest reference](configuration.md) for the complete list and
field behavior.

## Check the work

Run focused commands early, then the complete local suite:

```sh
make validate
make matrix
```

`make validate` invokes rsctf's offline parser and semantic checks with warnings
treated as errors. `make matrix` asks the same binary to validate the repository and
emit every direct service or generator Docker build context. Set
`RSCTF=/path/to/rsctf` when the matching binary is not on `PATH`.

GitHub Actions uses the same rsctf validation contract without requiring a copied
wrapper or repository-local checker. The manifest job imports the maintained action
directly:

```yaml
- name: Validate manifests with rsctf
  id: rsctf
  uses: dimasma0305/rsctf@main
```

The action selects the matching official rsctf image, pulls it, resolves the result
to an immutable digest, verifies its rsctf source/version labels, and runs
`/usr/local/bin/rsctf challenge check --github --deny-warnings /repository`. The
checkout is mounted read-only into a network-disabled, capability-free, read-only
container. It also runs `rsctf challenge matrix` and exposes the resulting
`container_matrix` and `container_count` outputs. Pin the `uses` ref to the matching
rsctf release tag after that release contains the action. For a commit-SHA action
pin, pass the matching exact `ghcr.io/dimasma0305/rsctf@sha256:...` through the
action's `image` input.

Container jobs are discovered automatically from these direct package paths:

```text
challenges/<mode>/<category>/<slug>/src/Dockerfile
challenges/<mode>/<category>/<slug>/generator/Dockerfile
```

Do not add a package to the GitHub Actions matrix or `Makefile` by hand. A `src/`
context becomes a service job; a `generator/` context is build-only. CI builds each
emitted context and runs service containers until their Docker `HEALTHCHECK` reports
healthy. This proves the image can start under the CI restrictions; it does not prove
flag rotation, checker verdicts, protocol correctness, or solvability.

Next exercise challenge-specific behavior in hidden staging and perform a
player-equivalent run using [Playtesting](playtesting.md). A healthy container or
working author solver confirms mechanics, not discoverability. Verify the organizer solution
against the exact candidate revision before starting a separate blind run that cannot read
it.

## Import safely

Repository Bindings finds the root `.gzevent` and recursively imports all
`challenge.yaml` files below it. The extra `challenges/` directory is only an
organizational layer. This example deliberately creates a hidden event and every
challenge starts disabled.

A rescan preserves the game row but deletes and recreates the challenges owned by
that event directory. Challenge IDs and challenge-level admin edits can therefore
change. Treat Git as the source of truth, and rehearse rescans on staging rather
than during a live event.

All committed flags are public. Replacing a value in the latest commit does not
erase it from Git history; rotate any value that was ever pushed.
