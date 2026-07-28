# Trusted API observer

This process runs outside the attackable hill and translates the demo
challenge's current controller into RSCTF's signed KotH observation protocol.
It reports only an exact team capability or JSON `null`; it cannot submit team
IDs, scores, durations, or formula inputs. RSCTF remains authoritative for
health confirmation, crown state, and fixed scoring.

## Security boundary

Never copy `RSCTF_KOTH_OBSERVER_SECRET` into `src/`, the hill image, a player
client, or a public log. Compromising the hill should let a team control the
hill, but must not reveal the credential of the independent observer. Run one
observer per hill under a dedicated OS or orchestrator identity, store its
environment in a restricted secret store, and use HTTPS with synchronized
system time.

The repository importer selects `src/` as the challenge image build context.
Therefore this sibling `observer/` directory is retained as documentation but
is not copied into the challenge image.

## RSCTF setup

1. Import the example and keep the game hidden with scoring paused.
2. Open **A&D / KotH operations**, choose the KotH view, and select
   **Enable API** for this challenge.
3. Copy the one-time secret immediately.
4. Start the official KotH lifecycle while still paused. The API context does
   not exist before the active crown cycle and target exist.
5. Configure this observer with a stable, observer-reachable hill URL. In
   Kubernetes this is normally a private Service name; do not use an ephemeral
   Pod IP.
6. Run `--once`, confirm the observation time in the operator view, then run
   continuously and resume scoring.

The claim source is frozen in the official snapshot. It cannot be switched
from marker mode to API mode after scoring starts.

A repository rescan recreates challenge rows and can change the challenge ID.
Stop the observer before a staging rescan, then enable API again and install the
new ID and one-time secret. Never rescan this binding during a live event.

## Run

Python 3.10 or newer is enough; the client has no third-party dependencies.
Read the secret interactively so it does not enter shell history:

```sh
export RSCTF_ORIGIN=https://ctf.example
export RSCTF_GAME_ID=7
export RSCTF_CHALLENGE_ID=42
export RSCTF_KOTH_HILL_URL=https://api-hill.internal.example
read -r -s -p 'Observer secret: ' RSCTF_KOTH_OBSERVER_SECRET
printf '\n'
export RSCTF_KOTH_OBSERVER_SECRET

python3 observer/observer.py --once
exec python3 observer/observer.py
```

Optional settings are:

| Variable | Default | Constraint |
| --- | ---: | --- |
| `RSCTF_KOTH_POLL_SECONDS` | `5` | `1..300`; unchanged state is not reposted |
| `RSCTF_KOTH_TIMEOUT_SECONDS` | `5` | `1..60` per HTTP request |

The observer fetches a fresh RSCTF context on every poll. It posts when either
the context or observed capability changes, uses a strictly increasing
Unix-millisecond timestamp, signs the exact compact JSON bytes, and retries
failures with bounded exponential backoff. A `409` therefore causes a fresh
context fetch instead of replaying stale state. It ignores ambient proxy
variables and refuses HTTP redirects so a compromised hill cannot steer its
trusted network client elsewhere. It never sends the observer secret to the
hill.

For loopback-only development, add `--allow-insecure-http`. Do not use that
flag for an event.

## Local regression test

From the repository root:

```sh
python3 scripts/test-koth-observer.py
```

The test runs fake RSCTF and hill endpoints, verifies the exact HMAC, checks
explicit uncaptured observations, confirms context changes are reposted, and
ensures unchanged state is deduplicated.
