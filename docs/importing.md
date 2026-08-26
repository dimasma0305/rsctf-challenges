# Importing with Repository Bindings

Import only a reviewed commit. Repository Bindings is an administrator trust
boundary: a scan reads manifests, archives source, builds local Docker contexts and
generators, and prepares checker dependencies.

Before the first hidden import, run both the repository checks and rsctf's own offline
preflight:

```sh
make validate
make validate-platform
make test-container-images
```

The CLI catches importer-schema and static package errors without a database. It does
not execute builds, install checker wheels, verify backend networking, or prove a
challenge is solvable, so it cannot replace the hidden staging scan and player smoke
test below.

The GitHub manifest job imports `dimasma0305/rsctf` and invokes the CLI from the
corresponding official rsctf image. The action resolves the pulled image to an
immutable digest before execution; an optional image override must be an exact
digest from the action repository's GHCR package. The local JavaScript validator
still checks this template's conventions, but it is additional coverage and is not
the platform compatibility authority.

## First hidden import

1. Push the intended revision to a repository and record the exact commit.
2. Sign in as an rsctf administrator and open **Admin → Repository Bindings**
   (`/admin/repo-bindings`).
3. Add the Git URL and branch. A public repository needs no token. For a private
   repository, use a fine-grained token with read-only contents access unless the
   workflow explicitly requires push-back.
4. Run **Scan now** and inspect the complete result. This example should report one
   event and nine challenge manifests.
5. Open the imported game. Confirm it is hidden and every challenge remains disabled.
6. Review every discovered service-image build, each deterministic generator
   build/replay result, all prepared checker suites, dependency pins, and any
   reported notice.
7. Set the real schedule and event policy in Admin. The sample `.gzevent` deliberately
   omits `start` and `end`; the importer supplies temporary defaults on first import.

Do not enable challenges from the scan result alone. Finish the
[release checklist](release-checklist.md) and exercise the imported player route with
a normal account first.

## What source builds do

Every container manifest here omits `containerImage`. A trusted scan archives the
whole package, selects the adjacent `src/` Docker context, and builds an internal
image. The deterministic variant example similarly builds `generator/Dockerfile` and
runs its deterministic replay contract.

Local and GitHub checks discover those same direct `src/Dockerfile` and
`generator/Dockerfile` paths automatically. Adding a package does not require editing
a CI matrix, but every new service still needs a named functional handler in
`scripts/test-container-images.py`. The handler key is the normalized
`<mode>-<category>-<slug>` image tag, so repeated slugs in different categories stay
isolated.

This source-build pattern requires the Docker builder and runtime owner to share the
same daemon. Kubernetes and deployments with independent node-local daemons need
reviewed images in a registry, pinned by immutable digest. Pin or mirror the base
image as well when the build host must avoid Docker Hub.

Before enabling a locally built service, inspect its build log and immutable image
identity, then test its port, resource limits, writable paths, flag delivery, and
restart behavior through the actual backend.

## Rescans are destructive to challenge rows

A rescan preserves the game row and operator-edited game settings, but clears and
recreates the challenges owned by this `.gzevent`. Challenge IDs and challenge-level
Admin edits can change. Git is the source of truth for challenge configuration.

Never casually rescan a running event. Rehearse the exact rescan on staging, account
for any IDs used by external automation, and confirm that all rebuilt services,
checkers, variants, and referees still refer to the new imported challenge records.

Event settings from `.gzevent` seed the game on its first import. Later scans preserve
operator changes such as the real schedule, which is why Git and Admin state must both
be reviewed before a live rescan.
