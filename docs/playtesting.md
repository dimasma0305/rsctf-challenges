# Playtesting

Playtesting answers a different question from automated testing: can a fresh player
understand and solve the challenge using only what the event actually gives them?

## First verify the build

From the repository root:

```sh
make test
```

When container or generator code changed, also run:

```sh
make test-container-images
```

This builds the images, waits for Docker health, and exercises each service's normal
protocol. Fix availability, checker, and build failures before asking someone to blind-solve.
Do not use the intended solver as the playtest; that tests mechanics, not clues.
The build list is discovered from package Dockerfiles. If a renamed or new service
has no matching normalized mode/category/slug case in
`scripts/test-container-images.py`, validation fails instead of skipping its runtime
check.

## Declare the player contract

Choose exactly one mode:

| Mode | Give the playtester | Do not give them |
| --- | --- | --- |
| service | public challenge copy and the issued URL or host/port | source, image, build logs, container access, or a handout that players do not receive |
| handout | byte-for-byte contents of the public `dist/` delivery | target, author notes, repository history, solver, or real flag |
| hybrid | the exact public target and exact public handout | any additional local artifact or privileged service access |

Write the contract down before starting. If the real event delivery is ambiguous,
resolve it with the author instead of choosing the more revealing option.

## Prepare an isolated room

Use the ignored root `playtest/` directory only as a staging convenience. Copy in
the public brief and declared handout files, if any. Start services and retain build
logs from the author workspace, outside the room. Use a redacted playtest flag.

`playtest/` is not a sandbox. For a credible blind run, give a fresh human account or
agent session a separate workspace containing only the prepared room. Do not inherit
the author conversation, intended chain, prior reports, parent filesystem, Git
history, container administration, process inspection, or undeclared localhost
services. Permit only the issued target and normal player-owned callbacks that the
real event permits.

A useful `PLAYER-BRIEF.md` is deliberately small:

```markdown
# Player brief

- Mode: service | handout | hybrid
- Target: exact public URL or host/port, if supplied
- Files: exact filenames, if supplied
- Public description: exact platform copy
- Time started: UTC timestamp
```

Do not add hints, implementation details, or organizer vocabulary that is absent
from the real challenge page.

## Run the playtest

Ask the player to record evidence as they work and allow them to stop. `solved`,
`partial`, `stuck`, `blocked-environment`, and `contaminated` are all useful results.
Do not answer a stuck question with a hint during the timed run.

Use this report shape:

```markdown
# Playtest report

## Result
- Verdict:
- Started/finished (UTC):
- Active time:

## Inputs received
- Target:
- Files:
- Public instructions:

## Timeline
- Time — observation — hypothesis — exact action — result

## Intended-looking progress
- Evidence and capability gained

## Guesses and clue gaps
- Non-obvious step and what, if anything, pointed to it

## Dead ends
- Action, evidence, and time spent

## Possible unintended paths
- Reproducible shortcut and boundary skipped

## Environment problems
- Failure and why it is environmental rather than challenge difficulty
```

## Review fairly

Compare each reported step with the intended trust-boundary transitions:

- A missing public breadcrumb is a clue defect, not extra difficulty.
- A working shortcut that skips a capability or identity boundary is an unintended
  solution even when it differs from the official solver.
- A source-assisted solve is not evidence for black-box discoverability.
- An environment outage or missing callback route requires a repaired rerun.
- Any inherited author knowledge makes the run contaminated.

After changing source, player copy, or artifacts, rebuild and start a fresh room. Do
not seed a new blind run with the old report.

## Screenshots and evidence

The bundled examples are mostly text and JSON, so this repository intentionally does
not ship screenshots that would quickly become stale. Add screenshots only when a
visual state materially proves something that text cannot.

For any screenshot you keep:

- capture the current build through the same route and identity available to a player;
- show the command for terminal output and never render a hand-written transcript;
- redact flags, tokens, production hostnames, and unrelated personal data;
- do not use container shells, internal logs, database views, or mocked browser state
  as player evidence;
- use descriptive names such as `ui-login.png`, `terminal-solve.png`, or
  `artifact-inspection.png`; and
- inspect the final image for clipping, stale controls, hidden secrets, and readable
  text before linking it from a guide or report.

Store temporary blind-run captures inside ignored `playtest/evidence/`. Move only
reviewed, still-current documentation images to `docs/assets/screenshots/`, creating
that directory when the first useful image exists.
