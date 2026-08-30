# Managed Leaderboard KotH reporting

Leaderboard King of the Hill challenges report bounded native evidence from the
platform-managed target. The challenge never calculates or submits rsctf points. rsctf
authenticates the target, binds evidence to the active lifecycle and settlement window,
resolves capability pseudonyms to eligible teams, normalizes objectives, validates the
Crown, and calculates the scoreboard result.

Use the complete example at
[`Koth/Web/managed-leaderboard-hill`](../challenges/Koth/Web/managed-leaderboard-hill/).
`src/reporter.py` runs inside the managed target and reads the same bounded in-memory
evidence state as the arena.

## Security boundary

When Leaderboard mode is enabled, rsctf injects these values into the managed target:

| Variable | Meaning |
| --- | --- |
| `RSCTF_KOTH_GAME_ID` | exact game scope |
| `RSCTF_KOTH_CHALLENGE_ID` | exact challenge scope |
| `RSCTF_KOTH_PLATFORM_URL` | private origin used to authenticate player capabilities |
| `RSCTF_KOTH_CONTEXT_URL` | exact active-context endpoint |
| `RSCTF_KOTH_OBSERVATION_URL` | exact evidence-submission endpoint |
| `RSCTF_KOTH_REPORTER_SECRET` | lifecycle-bound `koth_target_…` HMAC credential |

Do not author these values in `challenge.yaml`, Dockerfiles, Compose files, handouts, test
fixtures, logs, or solutions. The target must remain healthy when the variables are absent,
because rsctf creates the pre-cycle shared target before an operator enables Leaderboard
mode. A partial injected environment is a deployment error.

The credential authenticates only one game, hill, lifecycle, reset attempt, target,
container, and reporting revision. A compromised arena can forge its own native evidence
for that remaining lifecycle, but it cannot choose rsctf points, report for another hill,
or keep using the credential after reset. Keep reporter state and the credential in the
narrowest process that owns gameplay truth; never return either to players.

## Challenge contract

1. Exchange a submitted KotH capability with rsctf immediately and retain only the
   returned lowercase SHA-256 pseudonym.
2. Count only verified challenge actions. Views, polling, and unauthenticated traffic are
   not activity.
3. Publish the completion condition and ordered objective meanings before play.
4. Use unpredictable, expiring, one-use tasks or proofs and bind each result to the
   pseudonym that started it.
5. Keep evidence append-only, bounded, and replay-safe. A retention gap fails closed.
6. Filter evidence against the exact eligible hashes in the current context.
7. Submit finalized waves only inside rsctf's published settlement window. Include an
   empty wave or snapshot when nobody completed work.
8. Require acknowledgement counts to match the emitted snapshot. A mismatch fails closed.
9. Keep the functional checker read-only and independent of reporter state.
10. Report activity, objective ratios, and one unique-leader Crown assertion—never points.

The example uses 30-second proof waves and the ordered objectives `proof-strength` and
`solve-speed`. Every positive wave has one Crown only when it has a unique leader; a tie or
zero-result wave has none. rsctf applies its scoring formula after validating the snapshot.

## Enable and rehearse

1. Import the exact candidate revision into a hidden event with scoring paused.
2. Configure `RSCTF_KOTH_REPORTER_BASE_URL` on rsctf's lifecycle-owning role. On
   Kubernetes, also configure the exact reporter callback pod selector required by the
   platform deployment.
3. In **A&D / KotH operations**, choose **Enable Leaderboard** for the hill.
4. Let rsctf replace the pre-cycle target and inject a lifecycle-bound reporter credential.
5. Confirm the target is healthy and no response, log, process environment exposed to a
   child, or handout leaks an injected value.
6. Submit a preflight snapshot to freeze the ordered objective schema.
7. Exercise valid work, invalid capability, replay, stale capability, empty activity,
   reporter retry, and forced target recovery.
8. Verify submitted and recognized counts, functional checker evidence, and the scoreboard
   projection before resuming scoring.

The reporter signs the exact compact JSON body with HMAC-SHA256 over
`timestamp.gameId.challengeId.body`, using `RSCTF_KOTH_REPORTER_SECRET`. It posts to the
exact injected observation URL with `X-RSCTF-Timestamp` and
`X-RSCTF-Signature: sha256=<hex>`. Fetch the exact context URL before every changed
snapshot; do not derive a round or window locally.

## Verification

First validate the repository contract with the matching platform binary:

```sh
rsctf challenge check --deny-warnings .
```

Then build and run the image without reporter variables and confirm `/health` returns
exactly `ok`. In hidden staging, enable Leaderboard mode and verify capability exchange,
initial empty evidence, one valid proof, objective ordering, unique-Crown and tied-no-Crown
behavior, raw-token absence, acknowledgement counts, retry safety, and credential rotation
after target reset. Retain redacted evidence for the exact candidate revision.

For the full wire limits and deployment topology, use the rsctf organizer handbook that
matches the target release. The example source is the copyable package implementation;
the official binary and live API remain authoritative when prose differs.
