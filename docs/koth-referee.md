# Trusted Leaderboard referee

This process runs outside the player-facing hill. It reads the hill's bounded
event feed, filters events against the current capability hashes supplied by
RSCTF, aggregates integer evidence, signs the exact snapshot, and submits it to
RSCTF. It never sends raw capabilities or points.

## Security boundary

Never copy `RSCTF_KOTH_OBSERVER_SECRET` into `src/`, the hill image, a browser,
or a public log. Run the referee under a dedicated identity with:

- HTTPS to RSCTF and the private hill endpoint;
- synchronized system time;
- a persistent state path writable only by that identity;
- restricted network egress; and
- monitoring for feed gaps, context conflicts, and recognized-team mismatch.

The repository importer builds only `src/`. This sibling `observer/` directory
is therefore not copied into the attackable image. HMAC proves which referee
sent a snapshot; it does not prove that the referee is honest. Keep the
referee, its secret, and its state outside every player-controlled workload and
restrict its evidence access to read-only endpoints.

## What the example proves

The hill issues an unpredictable, expiring, one-use proof-of-work session.
Every solve attempt becomes an ordered event containing only the capability
hash, validity, proof-strength budget, and speed budget.

The referee divides play into challenge-native 30-second proof waves. It waits
two seconds after each boundary, freezes the result, and produces:

- completed activity `1 / 1` for every team with at least one valid proof in
  that wave;
- ordered objective IDs: `proof-strength`, then `solve-speed`;
- objectives: independently normalized evidence from completed proofs only.

For each positive wave, one unique best normalized result receives the Crown.
On an exact top-score tie, every tied team receives full relative-performance
credit and no team receives the Crown. RSCTF then applies its constant 95%
performance plus 5% Crown formula; the referee never sends points.

Failed attempts remain challenge telemetry; they neither add evidence nor
subtract points. A team quota is keyed by the capability hash rather than its
source IP, so changing IP addresses cannot let one team exhaust the shared
admission budget. Size the global budget for the rehearsed team count: a
field-wide resource failure voids the tick but can still disrupt play.

Unknown hashes are removed before submission. A cursor retention gap fails
closed. State is written atomically with mode `0600`, so a restart does not
duplicate accepted evidence or lose its strictly increasing timestamp.

## RSCTF setup

1. Import the example and leave the game hidden with scoring paused.
2. Open **A&D / KotH operations**, select KotH, and choose **Enable Leaderboard**.
3. Copy the one-time secret.
4. Start the official lifecycle while paused.
5. Configure a stable referee-reachable arena URL.
6. Run `--once`, confirm a current explicit-zero snapshot, exercise one valid
   and one invalid player action, wait for the wave to finalize, run `--once`
   again, and inspect the board.
7. Run continuously and resume scoring.

The `Api` source is frozen with the official hill. A repository rescan can
change staging configuration; rehearse it outside a live event.

## Run

Python 3.10 or newer is sufficient; no third-party package is required.

```sh
export RSCTF_ORIGIN=https://ctf.example
export RSCTF_GAME_ID=7
export RSCTF_CHALLENGE_ID=42
export RSCTF_KOTH_HILL_URL=https://leaderboard-hill.internal.example
export RSCTF_KOTH_STATE_FILE=/var/lib/rsctf-koth-referee/state.json
read -r -s -p 'Referee secret: ' RSCTF_KOTH_OBSERVER_SECRET
printf '\n'
export RSCTF_KOTH_OBSERVER_SECRET

python3 challenges/Koth/Web/api-observed-hill/observer/observer.py --once
exec python3 challenges/Koth/Web/api-observed-hill/observer/observer.py
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

1. fetches the exact active settlement context and eligible hashes;
2. retains a wave across a normal round change when that wave crosses the
   settlement boundary, assigning it by its server-confirmed end time;
3. resets its feed cursor only when a new cycle/reset replaces the container;
4. drains bounded evidence pages and rejects a cursor gap;
5. ignores pre-event history and events outside the eligible hash set;
6. freezes every complete 30-second wave after a two-second ingestion grace,
   including an empty team list when nobody finished;
7. constructs one compact, deterministic signed body containing every
   finalized wave in the current settlement window;
8. posts only when the current snapshot changed; and
9. requires submitted-wave and recognized-team counts to match.

RSCTF publishes contiguous settlement windows that close 20 seconds behind
the live round boundary. It waits for the cutoff before sampling, then allows
a bounded arrival period. A snapshot with no finalized waves is a valid fence
and awards nothing. Finalized waves are immutable; late evidence for one fails
closed instead of rewriting history. Updating the snapshot during the short
functional probe voids that checker round rather than producing inconsistent
scoring. Keep the polling interval short and monitor void frequency during
rehearsal. The wire contract caps one snapshot at 64 waves and 2,000 total
team-wave rows. Treat the last published window end as the event's scoring
cutoff and stop opening waves that cannot finalize before it.

## Verification

First validate the repository contract with the matching platform binary:

```sh
rsctf challenge check --deny-warnings .
```

That command checks the package and manifest statically; it does not execute the
referee. In hidden staging, run `observer/observer.py --once` with a dedicated test
identity and verify HMAC scope, the initial empty ledger, finalized objective budgets,
the unique-leader/no-Crown-on-tie rule, raw-token absence, stable objective identity,
unknown-hash filtering, deduplication, restart persistence, round fencing, feed-gap
failure, redirect refusal, and HTTPS-by-default URL checks. Retain redacted request,
response, and state evidence for the exact candidate revision.
