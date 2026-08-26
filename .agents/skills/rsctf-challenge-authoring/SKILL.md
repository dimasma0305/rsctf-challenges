---
name: rsctf-challenge-authoring
description: Create, edit, review, validate, or playtest challenge packages in an rsctf Repository Bindings repository. Use for manifests, challenge source, handouts, A&D/KotH checkers, deterministic generators, or challenge-release readiness; do not use for rsctf platform implementation work outside a challenge repository.
---

# rsctf Challenge Authoring

Keep challenge repositories easy to copy, safe to import, and honest about what a
player receives. Preserve existing rsctf manifest and runtime contracts unless the
request explicitly changes them.

## Route the task

Read each selected document completely before editing:

- New package, repository layout, or first-time authoring:
  [Getting started](../../../docs/getting-started.md)
- `.gzevent`, `challenge.yaml`, attachments, containers, A&D/KotH fields:
  [Manifest reference](../../../docs/configuration.md)
- A&D/KotH checker or verdict behavior:
  [Checker development](../../../docs/checkers.md)
- API-observed Leaderboard KotH referee:
  [Trusted KotH referee](../../../docs/koth-referee.md)
- Deterministic variants or trusted solve receipts:
  [Provenance](../../../docs/provenance.md)
- Blind solve, fairness, unintended path, or screenshot evidence:
  [Human playtest guide](../../../docs/playtesting.md) and
  [agent playtest boundaries](references/playtesting.md)
- Import, shipping, or final readiness review:
  [Repository Bindings](../../../docs/importing.md) and
  [release review](references/release-review.md)

For a cross-cutting request, read every applicable route. Do not read unrelated
references merely because they exist.

## Workflow

1. Inspect Git status, the closest example package, its manifest, relevant tests,
   and current player delivery contract. Preserve unrelated changes.
2. State whether the player receives a service, a handout, or both. Separate public
   player material from author source, secrets, solvers, and operational tooling.
3. Copy the closest cohesive package and delete components the new challenge does
   not need. Keep paths under `challenges/<mode>/<category>/<slug>/`.
4. Put behavior in its owning layer: manifest metadata in `challenge.yaml`, service
   code in `src/`, player files in `dist/`, checker protocol in `checker/run.py`,
   deterministic generation in `generator/`, and trusted referee logic in
   `observer/`.
5. Add or update focused regression coverage for contract changes. Keep inputs
   bounded, dependencies pinned, and secrets absent from source and evidence.
6. Run focused checks, `make test`, and `make validate-platform`. Confirm CI imports
   the maintained `dimasma0305/rsctf` action; do not vendor its wrapper into the
   challenge repository. The repository convention validator is
   additional coverage, not a replacement. When runtime or generator inputs
   changed, run `make test-container-images` so built services must
   become Docker-healthy and pass their player-visible protocol smoke test. Container
   contexts are discovered automatically; add a functional smoke handler for every
   new or renamed service instead of editing CI or Makefile image lists.
7. For readiness claims, require a player-equivalent blind run and hidden staging
   import; a solver run or green CI job alone is insufficient.

## Hard boundaries

- Start imported examples hidden and disabled. Do not use public Git flags in a real
  event or imply that rewriting history makes a disclosed value secret again.
- Omit `minScoreRate`, `difficulty`, and `submissionLimit` when rsctf's current
  Jeopardy defaults are intended. Add them only for a deliberate scoring-policy
  override, and omit them from A&D and KotH manifests.
- Never commit organizer tokens, observer HMAC secrets, private writeups, production
  hostnames, database dumps, container logs containing flags, or live credentials.
- A&D checkers must verify health and the current flag without mutating service state.
  KotH checkers receive no flag and must not inspect or alter the control source.
- Checkers have one target IP/port, bounded time and output, a read-only source/venv,
  and only exact wheel-installable PyPI pins.
- Do not present the included `DynamicAttachment` manifest as playable while rsctf
  lacks per-participation handout/flag assignment.
- Keep human maintainer documentation in `docs/`. Files intentionally delivered to
  players remain in `dist/` even when they are text.
- Do not invent screenshots. Capture the current player-visible state, or use text
  evidence when that communicates the result better.
