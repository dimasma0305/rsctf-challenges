# King-of-the-Hill checker template

Copy both `lib.py` and `run.py`; the checker needs both dependency-free files.
`lib.py` provides the protocol-neutral `KothContext`, verdict exceptions, and
`@koth_checker`. This demo's bounded HTTP request code and hill-health assertion
live in `run.py`. Replace its `http_get` function when the hill uses raw TCP,
binary framing, or another custom TCP protocol; the decorator still validates
`RSCTF_*` and maps outcomes to rsctf exit codes. Do not add `requirements.txt`
or external packages.

KotH checkers receive the target and round metadata, but no `RSCTF_FLAG`.
rsctf owns the capability-token marker protocol: it reads `/koth/king` before
and after this checker and attributes the stable value itself. A checker must
therefore verify health without reading or modifying the marker.

Start `src/app.py`, then run the decorated checker from the challenge directory:

```sh
RSCTF_ACTION=check \
RSCTF_TARGET_IP=127.0.0.1 \
RSCTF_TARGET_PORT=8080 \
RSCTF_ROUND=1 \
RSCTF_TEAM_ID=0 \
RSCTF_CHALLENGE_ID=1 \
python3 checker/run.py
echo $?
```

See the repository's `CHECKERS.md` for sandbox and verdict details.
