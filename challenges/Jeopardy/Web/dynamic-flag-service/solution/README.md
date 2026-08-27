# Dynamic Container: Personal Flag Service solution

> Organizer material. Do not expose it to a blind solver.

## Verification record

- Status: `draft`
- Revision: working tree; freeze after the exact commit is tested
- Challenge type: `DynamicContainer`
- Delivery: isolated service
- Artifact or image: pending final image identity
- Tested at: pending exact-instance run
- Command: `python3 solution/solve.py --url INSTANCE_URL`

## Summary

The issued instance prints its participation-specific flag at the HTTP root. The solver makes
one request and extracts it.

## Player inputs

- Target: the URL for the player's isolated instance.
- Public copy: another team's flag should not solve this instance.
- Not supplied: `RSCTF_FLAG`, container environment, service source, or organizer access.

## Walkthrough

1. Open the issued instance URL.
2. Read the `rsctf{...}` value in the plain-text response.
3. Submit that value for the same participation.

## Why it works

Author-side [`src/app.py`](../src/app.py) reads the injected `RSCTF_FLAG` environment value
when serving `/`. Each participation receives its own container and flag.

## Solver

```console
$ python3 solution/solve.py --url http://127.0.0.1:8080
rsctf{...}
```

## Evidence

The service has no visual UI. Preserve genuine HTTP output instead of a decorative screenshot.

## Notes

- Freeze only after cross-team flag rejection is verified on the intended backend.
- Never hard-code a generated team flag in this repository.
