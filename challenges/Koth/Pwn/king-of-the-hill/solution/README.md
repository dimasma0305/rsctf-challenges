# King of the Hill Demo: Claim Marker solution

> Organizer material. Never retain a live KotH token in this writeup or screenshots.

## Verification record

- Status: `draft`
- Revision: working tree; freeze after the exact commit is tested
- Challenge type: `KingOfTheHill`
- Delivery: shared marker service
- Artifact or image: pending final image identity
- Tested at: pending multi-team lifecycle run
- Command: `python3 solution/solve.py --url HILL_URL --token CURRENT_TOKEN`

## Summary

The player submits the team's current KotH token to `/claim`. The service stores it in the
marker file that rsctf reads when attributing control.

## Player inputs

- Target: shared hill URL.
- Capability: the team's current KotH token from rsctf.
- Public route: `/claim?token=...`.
- Not supplied: marker file access, other teams' tokens, or organizer controls.

## Walkthrough

1. Obtain the current team token from the platform.
2. URL-encode it as the `token` query value for `/claim`.
3. Confirm the service returns `claim recorded`.
4. Wait for rsctf to read the marker and attribute the hill.

## Why it works

Author-side [`src/app.py`](../src/app.py) atomically replaces `/koth/king` with the submitted
token. rsctf compares that value with current team capabilities.

## Solver

```console
$ python3 solution/solve.py --url http://127.0.0.1:8080 --token 'koth_REDACTED'
claim recorded
```

## Evidence

The claim and platform attribution are text/state evidence. Do not screenshot a reusable token.

## Notes

- A claim is not complete evidence until rsctf attributes the matching team.
- Freeze only after token rotation, reset, and competing-team claims are rehearsed.
