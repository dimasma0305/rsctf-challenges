# Attack & Defense BYOC: Flag File Service solution

> Organizer material. Do not include it in the BYOC bundle or service image.

## Verification record

- Status: `draft`
- Revision: working tree; freeze after the exact commit is tested
- Challenge type: `AttackDefense`
- Delivery: BYOC service
- Artifact or image: pending final image identity
- Tested at: pending full relay rehearsal
- Command: `python3 solution/solve.py --url http://TARGET`

## Summary

The team runs the supplied image behind the rsctf relay. The demo exposes the current rotating
flag at the public `/secret` route.

## Player inputs

- Target: opponent service URL or host/port exposed through the A&D network.
- Public clue: the root response names `/secret`.
- Team controls: only the BYOC host and containers allowed by the event.
- Not supplied: organizer source, relay administration, checker environment, or other teams' tokens.

## Walkthrough

1. Request `/` and read the route named by the service banner.
2. Request `/secret` through the opponent-facing service endpoint.
3. Submit the returned current-round `rsctf{...}` flag.

## Why it works

Author-side [`src/app.py`](../src/app.py) serves the flag file directly from `/secret`. It
reads the file per request so the BYOC agent can rotate flags without restarting the image.

## Solver

```console
$ python3 solution/solve.py --url http://127.0.0.1:8080
rsctf{...}
```

The solver is one bounded HTTP request and has no third-party dependency.

## Evidence

This service is plain text. Keep the genuine request and output instead of a browser screenshot.

## Notes

- Freeze only after the exact image, relay path, flag rotation, and team isolation pass.
- Replace the intentional direct disclosure before adapting this package into a real challenge.
