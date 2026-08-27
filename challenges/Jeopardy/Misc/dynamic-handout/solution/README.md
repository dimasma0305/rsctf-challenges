# Dynamic Attachment (illustrative): Per-Team Bundle solution

> This package documents an unsupported schema. It must remain disabled.

## Verification record

- Status: `draft`
- Revision: working tree
- Challenge type: `DynamicAttachment`
- Delivery: intended handout, currently incomplete
- Files: `README.txt` and `input.txt`
- Tested at: schema validation only
- Command: `python3 solution/solve.py --input dist/input.txt`
- Expected result: exit status `2` with `not playable`

## Summary

The importer accepts this manifest shape but does not assign a distinct imported attachment
and flag to each participation. There is no honest player solve for the current example.

## Player inputs

- Illustrative ZIP members: `README.txt` and `input.txt`.
- Public demo flags exist in the manifest but are not assigned per participation.
- Not supplied: a working generator or a participation-specific accepted flag mapping.

## Walkthrough

1. Inspect the bundle and observe that it labels itself illustrative-only.
2. Stop. Enabling or claiming a solve would misrepresent current rsctf behavior.

## Why it works

It does not currently work as a playable contract. The missing importer assignment step is a
platform limitation, not a puzzle for the player to infer.

## Solver

The required [`solve.py`](solve.py) fails explicitly:

```console
$ python3 solution/solve.py --input dist/input.txt
not playable: schema-only example: rsctf does not assign a per-participation handout and flag
```

## Evidence

Text and the nonzero exit status are sufficient. Do not create a fake successful screenshot.

## Notes

- Never mark this writeup `frozen` as a successful solve on the current importer.
- Revisit it only after distinct per-participation handout and flag assignment exists.
