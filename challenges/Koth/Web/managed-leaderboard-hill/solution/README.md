# King of the Hill Demo: Proof Arena solution

> Organizer material. Never store a live KotH capability or reporter secret here.

## Verification record

- Status: `draft`
- Revision: working tree; freeze after the exact commit is tested
- Challenge type: `KingOfTheHill` Leaderboard
- Delivery: shared HTTP service with managed in-target reporting
- Artifact or image: pending final image identity
- Tested at: pending complete managed-reporting lifecycle run
- Command: `python3 solution/solve.py --url HILL_URL --token CURRENT_TOKEN`

## Summary

The player exchanges a current KotH token for one short-lived proof-of-work puzzle. A counter
whose SHA-256 digest starts with the required zeros is submitted once and becomes bounded
evidence for the current wave.

## Player inputs

- Target: shared proof-arena URL.
- Capability: the team's current KotH token.
- Contract: `/start`, `/solve`, SHA-256, difficulty, counter bound, and expiry.
- Not supplied: reporter credential, evidence normalization state, or another team's token.

## Walkthrough

1. POST `{"token":"CURRENT_TOKEN"}` to `/start`.
2. Read `nonce`, `sessionId`, `difficulty`, and `maxCounter` from the response.
3. Test counters from zero upward until `sha256(nonce + ":" + counter)` starts with the
   advertised number of zero hexadecimal digits.
4. POST the session ID and counter to `/solve` before expiry.
5. Confirm `accepted: true`; the in-target reporter later submits the finalized wave.

## Why it works

The service exchanges the bearer token with rsctf, retains only the returned pseudonym, keeps
a one-use puzzle, and appends bounded evidence only for valid submissions. The in-target
reporter filters and submits normalized wave evidence; the player never calls a control API.

## Solver

```console
$ python3 solution/solve.py --url http://127.0.0.1:8080 --token 'koth_REDACTED'
accepted counter=12345 digest=0000...
```

[`solve.py`](solve.py) uses the server-advertised bounds and Python's standard library.

## Evidence

Requests and JSON responses are stronger than screenshots for this text API. Retain a trimmed,
redacted transcript during the final managed-reporting rehearsal.

## Notes

- A service acceptance proves challenge activity, not completed rsctf scoring.
- Freeze only after reporting, wave finalization, token rotation, and multi-team scoring pass.
