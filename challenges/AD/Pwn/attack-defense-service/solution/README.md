# Attack & Defense Demo: Raw TCP Flag Service solution

> Organizer material. Do not put this directory in a player handout or playtest room.

## Verification record

- Status: `draft`
- Revision: working tree; freeze after the exact commit is tested
- Challenge type: `AttackDefense`
- Delivery: managed service
- Artifact or image: pending final image identity
- Tested at: pending exact-target run
- Command: `python3 solution/solve.py --host TARGET --port PORT`

## Summary

The service exposes a newline-based TCP protocol. Sending `GET_FLAG` returns the current
rotating flag without authentication.

## Player inputs

- Target: one opponent host and port from rsctf.
- Public protocol: `PING` returns `PONG`; `GET_FLAG` returns the flag.
- Not supplied: service source, checker source, flag file, or container access.

## Walkthrough

1. Connect to the issued TCP target.
2. Send the documented command `GET_FLAG` followed by a newline.
3. Read one response line and submit the returned `rsctf{...}` value.

The line itself is the gained capability. No additional exploit stage exists in this
educational orchestration example.

## Why it works

Author-side source in [`src/app.py`](../src/app.py) maps `GET_FLAG` directly to the current
flag file. The service reads the file on every request, so the same solve works after round
rotation.

## Solver

[`solve.py`](solve.py) uses only the Python standard library:

```console
$ python3 solution/solve.py --host 127.0.0.1 --port 8080
rsctf{...}
```

## Evidence

The protocol is text-only, so genuine command output is clearer than a screenshot.

## Notes

- The checker must remain read-only and retrieve the same current flag.
- A real A&D challenge must replace this deliberately unauthenticated smoke-test behavior.
- Freeze this writeup only after a two-team rotation rehearsal.
