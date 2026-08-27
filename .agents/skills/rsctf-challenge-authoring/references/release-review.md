# Release review

Use this reference when asked whether a challenge is ready to import, publish, or run.

## Review inputs

Inspect the exact proposed revision, `git status`, manifest, player artifacts, build
contexts, dependencies, checker/generator/referee code, automated results, blind
playtest report, and staging scan evidence. Do not infer a pass from the intended
solver or from an earlier revision.

## Required evidence

- `make validate` and `make matrix` pass with the official rsctf binary matching the
  target release. Applicable container/generator builds pass on the target
  architecture, the generated matrix contains every direct package Dockerfile, and
  every service declares and passes its Docker `HEALTHCHECK`.
- Docker health is only an availability gate. The player-visible protocol, checker
  verdicts, flag delivery/rotation, and generator replay contract have independent
  hidden-staging evidence where applicable.
- Player artifacts contain exactly the declared delivery and no real flag, solution,
  hidden source, repository history, organizer material, or credentials.
- Service behavior was exercised through the player-visible route with realistic
  resource, restart, and flag-delivery behavior.
- A fresh isolated player run supports the clue fairness and difficulty assessment;
  high/critical unintended paths have been fixed and rerun.
- A hidden, disabled staging import reports the expected event/challenges and build
  results. Normal users cannot cross hidden or pre-start boundaries.
- A&D/KotH changes have real multi-team lifecycle evidence. An API-observed referee
  keeps its secret/state outside player-controlled workloads.

Report missing evidence explicitly. Do not describe the challenge as ready when the
only evidence is local syntax validation, a known solver, a commit, or green CI.
