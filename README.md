# rsctf challenge repository

A copyable, safe-by-default example repository for rsctf **Repository Bindings**.
It contains one hidden event and nine small challenges covering every supported
challenge type. Challenge packages live under `challenges/`; human guidance lives
under `docs/`; AI-agent guidance lives under `.agents/` and `AGENTS.md`.

> Every flag committed here is public demo data. Replace it before using a copied
> challenge in a real event, and assume the old value remains visible in Git history.

## Fast path

From the repository root:

```sh
make help
make list
make validate
make matrix
```

Then follow the [playtest guide](docs/playtesting.md) before asking an organizer to
import or enable the challenge. Both commands use the official `rsctf` binary, so
install the version that matches the release you will import into. CI imports
`dimasma0305/rsctf` as a reusable action; this repository contains no validation or
container-discovery scripts of its own.

To make a challenge:

1. Read [Getting started](docs/getting-started.md).
2. Use the [authoring contract](docs/authoring-contract.md) to choose the exact package
   components, then copy the closest package under `challenges/`.
3. Change its slug, `challenge.yaml`, player files, source, and checker as needed. Keep
   the tracked organizer writeup and simple solver in the format defined by
   [Solutions and reference solvers](docs/solutions.md).
4. Run `make validate` and `make matrix`. CI builds every context emitted by rsctf
   and waits for each service image's Docker `HEALTHCHECK` to pass.
5. Give a fresh player only the declared service and/or handout contract.
6. Complete the [release checklist](docs/release-checklist.md).

## Repository map

```text
.
├── .agents/                         # implicitly selectable Codex skill suite
├── .github/workflows/validate.yml   # CI validation and container builds
├── .gzevent                         # one hidden rsctf event
├── AGENTS.md                        # entry point for AI coding agents
├── Makefile                         # memorable local commands
├── challenges/
│   ├── AD/<category>/<slug>/         # manifest + only required components
│   ├── Jeopardy/<category>/<slug>/
│   └── Koth/<category>/<slug>/
├── docs/                            # human documentation and checklists
└── README.md                        # this short entry point
```

The importer recursively discovers `challenge.yaml` below the root `.gzevent`, so
the organizational `challenges/` directory does not change the rsctf wire contract.
Every imported challenge starts disabled, and this example event starts hidden.

## Documentation

Start at the [documentation index](docs/README.md). The most-used pages are:

- [Getting started](docs/getting-started.md)
- [Challenge authoring contract](docs/authoring-contract.md)
- [Manifest reference](docs/configuration.md)
- [Solutions and reference solvers](docs/solutions.md)
- [Checker development](docs/checkers.md)
- [Playtesting](docs/playtesting.md)
- [Importing with Repository Bindings](docs/importing.md)
- [Release checklist](docs/release-checklist.md)
- [Provenance and deterministic variants](docs/provenance.md)
- [Managed Leaderboard KotH reporting](docs/koth-reporting.md)

AI agents should begin with [AGENTS.md](AGENTS.md). Start Codex from this repository root
or a directory below it so the repository-local skills are discovered. The integrated suite
routes design, organizer solutions, blind playtests, report review, and release
review separately. Matching requests can select a skill automatically; teammates can force
a specific workflow with names such as `$rsctf-challenge-playtest`.
