# King-of-the-Hill checker template

Copy both `lib.py` and `run.py`; the checker needs both dependency-free files.
`lib.py` provides the protocol-neutral `KothContext`, verdict exceptions, and
the `@checker` / `run_koth_checker()` suite API. The legacy single-function
`@koth_checker` wrapper remains available. This demo's bounded HTTP request code
lives in `run.py`; separate focused functions check `/health` and the public
banner. The runner cryptographically shuffles them, attempts each once, and
combines any failures with deterministic verdict priority. Each check must be
read-only and order-independent. Replace `http_get` and the whole suite when the
hill uses another TCP protocol.

This HTTP example intentionally needs no `requirements.txt`. If an adapted
checker needs a package, use the exact, wheel-only PyPI pin format documented in
the repository's `CHECKERS.md`.

KotH checkers receive the target and round metadata, but no `RSCTF_FLAG`.
rsctf owns the capability-token marker protocol: it reads `/koth/king` before
and after this checker and attributes the stable value itself. A checker must
therefore verify health without reading or modifying the marker.

Start `src/app.py`, then run the shuffled checker suite from the challenge directory:

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
