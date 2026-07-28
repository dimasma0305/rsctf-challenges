# Trusted API arena referee

This process runs outside the player-facing arena. It reads the arena's bounded
event feed, filters events against the current capability hashes supplied by
RSCTF, aggregates integer evidence, signs the exact snapshot, and submits it to
RSCTF. It never sends raw capabilities or points.

## Security boundary

Never copy `RSCTF_KOTH_OBSERVER_SECRET` into `src/`, the arena image, a browser,
or a public log. Run the referee under a dedicated identity with:

- HTTPS to RSCTF and the private arena endpoint;
- synchronized system time;
- a persistent state path writable only by that identity;
- restricted network egress; and
- monitoring for feed gaps, context conflicts, and recognized-team mismatch.

The repository importer builds only `src/`. This sibling `observer/` directory
is therefore not copied into the attackable image.

## What the example proves

The arena issues an unpredictable, expiring, one-use proof-of-work session.
Every solve attempt becomes an ordered event containing only the capability
hash, validity, proof-strength budget, and speed budget.

The referee produces:

- activity: up to five valid solutions per tick;
- objectives: independently normalized proof strength and speed;
- integrity: valid attempts divided by all solve attempts.

Unknown hashes are removed before submission. A cursor retention gap fails
closed. State is written atomically with mode `0600`, so a restart does not
duplicate accepted evidence or lose its strictly increasing timestamp.

## RSCTF setup

1. Import the example and leave the game hidden with scoring paused.
2. Open **A&D / KotH operations**, select KotH, and choose **Enable API**.
3. Copy the one-time secret.
4. Start the official lifecycle while paused.
5. Configure a stable referee-reachable arena URL.
6. Run `--once`, confirm a current explicit-zero snapshot, exercise one valid
   and one invalid player action, run `--once` again, and inspect the board.
7. Run continuously and resume scoring.

The `Api` source is frozen with the official hill. A repository rescan can
change staging configuration; rehearse it outside a live event.

## Run

Python 3.10 or newer is sufficient; no third-party package is required.

```sh
export RSCTF_ORIGIN=https://ctf.example
export RSCTF_GAME_ID=7
export RSCTF_CHALLENGE_ID=42
export RSCTF_KOTH_HILL_URL=https://api-arena.internal.example
export RSCTF_KOTH_STATE_FILE=/var/lib/rsctf-koth-referee/state.json
read -r -s -p 'Referee secret: ' RSCTF_KOTH_OBSERVER_SECRET
printf '\n'
export RSCTF_KOTH_OBSERVER_SECRET

python3 observer/observer.py --once
exec python3 observer/observer.py
```

Optional settings:

| Variable | Default | Constraint |
| --- | ---: | --- |
| `RSCTF_KOTH_POLL_SECONDS` | `5` | `1..300` |
| `RSCTF_KOTH_TIMEOUT_SECONDS` | `5` | `1..60` seconds per request |
| `RSCTF_KOTH_STATE_FILE` | none | use a persistent restricted path in production |

For loopback development only, add `--allow-insecure-http`.

## Behavior

On every poll, the referee:

1. fetches the exact active round context and eligible hashes;
2. resets accumulated team evidence on a new round;
3. resets its feed cursor only when a new cycle/reset replaces the container;
4. drains bounded evidence pages and rejects a cursor gap;
5. ignores events outside the active round or eligible hash set;
6. constructs one compact, deterministic signed body;
7. posts only when the current snapshot changed; and
8. requires submitted and recognized team counts to match.

RSCTF waits at most six seconds for the first exact current-round snapshot,
then may sample at any point in the round. Updating evidence during the short
functional probe voids that tick rather than producing inconsistent scoring.
Keep the polling interval below that arrival window and monitor void frequency
during rehearsal.

## Regression test

From the challenge repository root:

```sh
python3 scripts/test-koth-observer.py
```

The test verifies HMAC scope, initial zero, objective budgets, raw-token
absence, unknown-hash filtering, deduplication, persistent restart, round
fencing, feed-gap failure, redirect refusal, and HTTPS-by-default URL checks.
