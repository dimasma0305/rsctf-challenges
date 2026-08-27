# Deterministic Variant: Team Sum solution

> Organizer material. Generated team inputs and retained output must remain redacted.

## Verification record

- Status: `draft`
- Revision: working tree; freeze after the exact commit is tested
- Challenge type: `StaticAttachment` with `PerParticipation` variants
- Delivery: generated handout content
- Shared attachment SHA-256: `cecc92f3958a1bff6a07cb403199e14345ead45772024edd2dd2ddde87068cb6`
- Tested at: local arithmetic smoke test
- Command: `python3 solution/solve.py LEFT RIGHT`

## Summary

Each participation receives two deterministic integers. Their decimal sum becomes the suffix
of `rsctf{sum_RESULT}`.

## Player inputs

- Generated content: two visible integers and the flag format.
- Shared file: `README.txt` explaining that the question is generated separately.
- Not supplied: generator seed, server-side generated flag, or organizer automation.

## Walkthrough

1. Read the two integers in the generated challenge content.
2. Add them using ordinary decimal arithmetic.
3. Insert the result into `rsctf{sum_RESULT}` and submit it.

## Why it works

The trusted generator derives both integers from one immutable seed and constructs the
accepted flag from their sum. Identical variant input produces identical output.

## Solver

```console
$ python3 solution/solve.py 1234 5678
rsctf{sum_6912}
```

[`solve.py`](solve.py) contains only the addition and CLI arguments.

## Evidence

The generated question and solver output are text. A screenshot would add no useful evidence.

## Notes

- Record the exact generated participation identity when freezing a real verification.
- Re-run deterministic replay after any generator change.
