# Repository manifest reference

This page describes the configuration that the current rsctf Repository
Bindings importer actually consumes. The manifests in `AD/`, `Koth/`, and
`Jeopardy/` are complete, importable examples; copy the closest one and change
only what your challenge needs.

## Repository layout

One `.gzevent` creates one game and owns every `challenge.yaml` below its
directory. This repository additionally enforces a readable convention:

```text
AD/<category>/<challenge>/challenge.yaml
Koth/<category>/<challenge>/challenge.yaml
Jeopardy/<category>/<challenge>/challenge.yaml
```

The category directory must be one of `Misc`, `Crypto`, `Pwn`, `Web`,
`Reverse`, `Blockchain`, `Forensics`, `Hardware`, `Mobile`, `PPC`, `AI`,
`Pentest`, or `OSINT`.

## Event manifest

Event settings seed a game only on its first import. A rescan preserves later
game-level edits made in Admin, but deletes and recreates its challenges.

| `.gzevent` key | Default | Notes |
| --- | --- | --- |
| `title` | required | Must be non-empty; give every imported event a stable, unique title |
| `start` | import time + 1 day | ISO-8601 timestamp |
| `end` | import time + 30 days | ISO-8601 timestamp |
| `hidden` | `false` | Use `true` until review and staging are complete |
| `summary`, `content` | empty | Player-facing Markdown content |
| `acceptWithoutReview` | `false` | Whether new team joins are accepted automatically |
| `inviteCode` | absent | Optional event join code |
| `teamMemberCountLimit` | `0` | `0` means the normal unlimited/default behavior |
| `containerCountLimit` | `3` | Per-team normal-container limit |
| `practiceMode` | `true` | Allows supported post-event practice behavior |
| `writeupRequired` | `false` | Require a writeup submission |
| `writeupDeadline` | import time + 30 days | ISO-8601 timestamp |
| `writeupNote` | empty | Writeup instructions |
| `bloodBonus` | platform packed default | Internal packed value; configure percentages in Admin |

`poster` and `organizations` are accepted by the parser but are not currently
applied when the game is created. Do not rely on them in a repository template.

The event-wide `ad:` block supports:

| Key | Purpose |
| --- | --- |
| `tickSeconds` | Round cadence |
| `flagLifetimeTicks` | Number of rounds a flag remains valid (`1..50`) |
| `warmupSeconds` | Delay before round/scoring activity starts |
| `resetCooldownMinutes` | Cooldown between managed-service resets |
| `allowSnapshotDownload` | Allow managed-service snapshot downloads |
| `snapshotRetentionDays` | Persisted, but not currently read by runtime behavior |
| `getflagWindowFraction` | Persisted, but not currently read by runtime behavior |
| `minGracePeriodSeconds` | Persisted, but not currently read by runtime behavior |

See [`.gzevent`](.gzevent) for a safe staging configuration.

## Common challenge keys

| Key | Default | Notes |
| --- | --- | --- |
| `name` | required | Display name |
| `author` | absent | Rendered above the description |
| `description` | empty | Markdown/HTML challenge text |
| `type` | required | A supported type shown in the copyable-examples table below |
| `category` | inferred/`Misc` | Explicit category should match its directory |
| `minScoreRate` | `0.25` | Dynamic-score floor, clamped to `0..1` |
| `difficulty` | `5` | Positive dynamic-score decay factor |
| `submissionLimit` | `0` | `0` means no explicit attempt limit |
| `hints` | absent | String list |
| `flags` | absent | Static flag rows for attachment/container challenges; imported `DynamicAttachment` rows are not yet assigned per team; do not use for A&D or KotH |
| `flagTemplate` | absent | Flag generator for `DynamicContainer` and A&D; use `[TEAM_HASH]` and, when rotation is needed, `[GUID]` |
| `provide` | `dist/` convention | Attachment file or directory relative to the manifest |
| `disableBloodBonus` | `false` | Disable first-solve bonuses for this challenge |
| `ignore` | `false` | `true` prevents creation and is rejected by this catalog validator |

Do not add `value`: the repository importer always creates a 1000-point Standard
challenge and ignores unknown keys. Only `minScoreRate` and `difficulty` control
the imported jeopardy score curve. Other misleading, ignored keys include
`scoreCurve`, `originalScore`, `deadline`, `networkMode`, `isEnabled`, and
`adScoringWeight`.

## Container block

`StaticContainer`, `DynamicContainer`, `AttackDefense`, and `KingOfTheHill` use
`container:`:

| Key | Behavior |
| --- | --- |
| `containerImage` | Omit to build `src/Dockerfile` (then package-root `Dockerfile`); a concrete reference switches to registry pull/pin behavior |
| `flagTemplate` | Container-local override for the top-level template |
| `memoryLimit` | Memory limit in MiB; defaults to 64 for Jeopardy/KotH and 256 for managed A&D |
| `cpuCount` | Backend-specific CPU limit; use `1` for the portable examples |
| `storageLimit` | Persisted, but not currently enforced by the runtime |
| `exposePort` | Service port inside the challenge container |
| `enableTrafficCapture` | Effective only for platform-hosted A&D services today; omit it elsewhere |
| `enableSharedContainer` | Effective only for `StaticContainer`; all teams share one instance |

This repository deliberately omits every `containerImage`, so Repository
Bindings builds the checked-in source. Local archive builds require the Docker
backend and one daemon shared by the builder and container owner. Kubernetes or
independent node-local daemons need a prebuilt immutable registry image instead.

## A&D and KotH block

`AttackDefense` and `KingOfTheHill` use `ad:`:

| Key | Import default | Behavior |
| --- | --- | --- |
| `checkerImage` | absent | Omit it; concrete checker-container references are rejected, while an adjacent `checker/run.py` entry point and its sibling source files are prepared automatically |
| `allowEgress` | `false` | Controls outbound networking for platform-managed A&D and KotH containers, not checker or BYOC-host egress |
| `allowSelfReset` | `true` | Player reset for managed A&D; unavailable for BYOC |
| `sshRequiresFlag` | `false` | Persisted but not currently enforced by SSH authorization; omit it from runnable templates |
| `selfHosted` | `false` | `true` selects BYOC and is valid only for `AttackDefense` |

Put a `checker/` directory beside every A&D or KotH manifest. Copy the complete
directory from the closest example: `lib.py` supplies the protocol-neutral
contexts, verdicts, `@checker` registry, and `run_ad_checker()` /
`run_koth_checker()` entry points; the legacy `@ad_checker` and `@koth_checker`
wrappers remain available. `run.py` owns the challenge protocol and assertions.
An optional `requirements.txt` beside `run.py` may contain only simple, exactly
pinned PyPI packages such as
`pwntools==4.15.0`; URLs, local paths, editable installs, pip options, and
unpinned or ranged versions are rejected. Repository Bindings installs these
packages and their dependencies into the immutable checker environment using
wheels only, so preparation fails when a compatible wheel cannot be resolved.

The managed Pwn example demonstrates a newline-framed raw TCP checker using
`pwntools==4.15.0`; the self-hosted Web example uses `httpx==0.28.1`; KotH keeps
its standard-library HTTP implementation and needs no requirements. Dependency
resolution requires PyPI access during a trusted repository scan or admin
approval. Review the repository commit and package pins before preparing them.
See [`CHECKERS.md`](CHECKERS.md).

The examples register focused checks whose execution order is cryptographically
and independently shuffled for each checker process. A fresh shuffle may repeat
an earlier order. Every registered function is attempted once; none is randomly
skipped, and source-registration order is not execution order.
Failures do not skip later checks; the final priority is InternalError, Offline,
Mumble, then OK.
The A&D suite as a whole must cover full service health and the current flag.
Checks must be read-only and order-independent. Order and fingerprint variation
is only defense-in-depth: it does not hide the checker source IP or by itself
prevent source-IP allowlisting.

Use these two A&D examples to compare the hosting modes:

```yaml
# Platform-hosted: rsctf launches one service container per accepted team.
ad:
  allowEgress: false
  allowSelfReset: true
  selfHosted: false
```

```yaml
# Self-hosted/BYOC: each team runs the downloaded service behind a relay.
ad:
  selfHosted: true
```

For KotH, use only settings that affect the platform-owned hill:

```yaml
ad:
  allowEgress: false
```

Even in BYOC mode, keep a local `src/Dockerfile`: rsctf builds it during import
and streams the immutable challenge-service image to authorized teams. The BYOC
tunnel must be routed to a network-capable rsctf role. The generated bundle also
uses the separately configured BYOC relay-agent image; mirror that platform
dependency and all base images for a completely Docker-Hub-free deployment.

## Copyable examples

| Type/mode | Example |
| --- | --- |
| `StaticAttachment` | [`Jeopardy/Misc/static-handout`](Jeopardy/Misc/static-handout/) |
| `DynamicAttachment` | [`Jeopardy/Misc/dynamic-handout`](Jeopardy/Misc/dynamic-handout/) — schema only; current per-team assignment is incomplete |
| shared `StaticContainer` | [`Jeopardy/Web/static-flag-service`](Jeopardy/Web/static-flag-service/) |
| per-team `DynamicContainer` | [`Jeopardy/Web/dynamic-flag-service`](Jeopardy/Web/dynamic-flag-service/) |
| platform-hosted `AttackDefense` | [`AD/Pwn/attack-defense-service`](AD/Pwn/attack-defense-service/) |
| self-hosted `AttackDefense` | [`AD/Web/self-hosted-service`](AD/Web/self-hosted-service/) |
| `KingOfTheHill` | [`Koth/Pwn/king-of-the-hill`](Koth/Pwn/king-of-the-hill/) |

For custom functional checks, continue with [`CHECKERS.md`](CHECKERS.md).
