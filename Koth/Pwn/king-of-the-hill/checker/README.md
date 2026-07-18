# King-of-the-Hill checker template

KotH checkers receive the target and round metadata, but no `RSCTF_FLAG`.
rsctf owns the capability-token marker protocol: it reads `/koth/king` before
and after this checker and attributes the stable value itself. A checker must
therefore verify health without reading or modifying the marker.

Start `src/app.py`, then run from the challenge directory:

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
