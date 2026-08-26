# Agent playtest boundaries

Use this reference for a blind solve, fairness review, or unintended-solution check.

## Select the exposure mode

- `service`: public copy and exact target only. Repository source, images, build logs,
  handouts not issued by the platform, container/process inspection, and hidden
  localhost services are author-only.
- `handout`: exact player files only. Do not invent a service or read parent source,
  history, the intended solver, the real flag, or prior reports.
- `hybrid`: exact public copy, target, and player files. Nothing else is implied.

When the contract is ambiguous, ask the author. Never choose the more revealing mode
to make the solve easier.

## Isolation

Prepare the target and artifacts from the author workspace, then start a fresh agent
with no inherited challenge discussion. Restrict its filesystem to the clean room and
its network to declared targets plus normal player-owned callback capability. A
gitignored `playtest/` directory or nested Git marker is not an operating-system
sandbox and does not prove isolation.

Mark a run contaminated if the solver receives author source not issued to players,
the intended chain, prior report, repository history, real flag, privileged logs,
container administration, undeclared ports, or a hint during the run.

## Report

Record UTC start/finish times and each observation, hypothesis, exact action, result,
capability gained, guess, dead end, and possible shortcut. Valid outcomes are
`solved`, `partial`, `stuck`, `blocked-environment`, or `contaminated`.

Do not turn an environment failure into a difficulty judgment. Do not call a
source-assisted run black-box. Treat an unexplained required leap as a clue defect and
a reproducible boundary-skipping shortcut as a challenge defect.

Screenshots must be genuine current-build evidence from the player-visible route.
Never create a fake UI, hand-written terminal transcript, or author-only source view
to fill an evidence gap.
