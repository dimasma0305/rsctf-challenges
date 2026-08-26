# Release checklist

Use this before requesting a Repository Bindings scan or enabling a challenge. Read
[Importing with Repository Bindings](importing.md) for the scan/rescan lifecycle. A
checked box means the behavior was observed on the exact revision being proposed.

## Package

- [ ] The package is under `challenges/<mode>/<category>/<slug>/` and the manifest
      category matches the directory.
- [ ] Player copy states the objective without leaking the intended exploit.
- [ ] `dist/` contains exactly the files players receive, with no solver, writeup,
      source, history, real flag, or organizer notes unless source is intentionally
      part of the challenge.
- [ ] Container and generator build contexts contain no credentials, private keys,
      observer secrets, admin tokens, or production-only configuration.
- [ ] Every dependency is necessary, reviewed, and pinned appropriately.
- [ ] All committed flags are treated as disclosed and replaced for the real event.

## Functional verification

- [ ] `make validate-platform` passes with the official checker matching the target
      rsctf release.
- [ ] GitHub Actions passes the imported `dimasma0305/rsctf` step, pinned to the
      target rsctf release (or to an action commit plus matching exact image digest).
- [ ] `make test` passes.
- [ ] `make test-container-images` passes when a service build context changed;
      `make build-containers` passes for generator-only changes.
- [ ] Every direct `src/Dockerfile` and `generator/Dockerfile` appears in the
      dynamically generated matrix; no package is maintained in a hand-written CI list.
- [ ] Every discovered service's normalized mode/category/slug tag has an independent
      functional handler in `scripts/test-container-images.py`; generators remain
      explicitly build-only.
- [ ] Every long-running service image declares a Docker `HEALTHCHECK`, reaches
      `healthy`, and then passes an independent protocol-level smoke request.
- [ ] The service was exercised through the same protocol and exposed port players
      will use, including failure and timeout behavior.
- [ ] A&D checks retrieve the current rotating flag through player-visible behavior.
- [ ] KotH checks are read-only and do not read or alter the ownership/control source.
- [ ] Resource limits, writable paths, restarts, and flag rotation were tested on the
      intended container backend.

## Player verification

- [ ] A fresh playtester received only the declared service/handout/hybrid contract.
- [ ] The run was isolated from author notes, source not issued to players, solver,
      repository history, old reports, logs, and container administration.
- [ ] Required non-obvious transitions have visible breadcrumbs.
- [ ] High- and critical-severity unintended paths are fixed and retested.
- [ ] Difficulty is based on the blind report, not only the author's solve time.
- [ ] Any retained screenshot is current, player-equivalent, readable, and redacted.

## Hidden staging import

- [ ] `.gzevent` remains hidden and the imported challenges remain disabled.
- [ ] The scan reports one event and the expected challenge count.
- [ ] Every local service/generator build completed and its log was reviewed.
- [ ] A normal non-admin player account can access only the intended pre-start and
      player-visible surfaces.
- [ ] A rescan was rehearsed away from a live event; challenge ID/admin-edit churn is
      understood.
- [ ] A&D or KotH changes passed a full multi-team lifecycle rehearsal, including
      scheduling, VPN/BYOC paths, flag delivery, checking, reset, and scoring.
- [ ] The signed KotH referee, when used, runs outside player workloads with its
      secret and persistent state restricted to its dedicated identity.

Do not enable the illustrative `DynamicAttachment` example: the current importer
accepts the schema but does not yet assign distinct per-team downloads and flags.
