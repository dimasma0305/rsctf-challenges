# Static Attachment: Welcome File solution

> Organizer material. The committed example flag is public demo data.

## Verification record

- Status: `draft`
- Revision: working tree; freeze after the exact commit is tested
- Challenge type: `StaticAttachment`
- Delivery: handout
- Handout SHA-256: `4dcc990732db746be5a384cc323bfb049ebf93723460191ef0027125e9b4e7fd`
- Tested at: local file smoke test
- Command: `python3 solution/solve.py --input dist/welcome.txt`

## Summary

The player reads one UTF-8 text file. Its final line contains the flag.

## Player inputs

- File: `welcome.txt` with the SHA-256 value above.
- Hint: the attachment is plain UTF-8 text.
- Not supplied: additional service or organizer state.

## Walkthrough

1. Open `welcome.txt` with any text viewer.
2. Read the line beginning with `Demo flag:`.
3. Submit the `rsctf{...}` value on that line.

## Why it works

`StaticAttachment` gives every team the same file, and the manifest accepts the same static
flag. This is intentionally the smallest repository-binding example.

## Solver

```console
$ python3 solution/solve.py --input dist/welcome.txt
rsctf{...}
```

The solver reads the file and extracts one rsctf flag with a bounded regular expression.

## Evidence

The attachment is six lines of text. A screenshot is less clear than the exact file and command.

## Notes

- Replace the disclosed demo flag before copying this package into a real event.
- Recompute the handout hash after any byte changes.
