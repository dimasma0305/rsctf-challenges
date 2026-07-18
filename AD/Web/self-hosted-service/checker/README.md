# Self-hosted checker template

Copy `lib.py`, `run.py`, and `requirements.txt` together. `lib.py` provides the
protocol-neutral `AdContext`, verdict exceptions, `@checker`, and
`run_ad_checker()`. The legacy single-function `@ad_checker` wrapper remains
available. This demo's bounded HTTP request code and service assertions live in
`run.py`, using the exact `httpx==0.28.1` pin. Redirects and proxy environment
variables are disabled, and the response is streamed into a fixed-size buffer.

Two focused `@checker` functions collectively validate `/health` and the current
flag at `/secret`. `run_ad_checker()` cryptographically shuffles the registry
and attempts every function once. The whole suite must cover complete health
and current-flag validation; individual checks must be read-only and cannot
depend on another check running first. Replace `http_get` and the complete suite
when your service uses raw TCP, binary framing, or another custom TCP protocol.
Changing request order is only defense-in-depth: it does not hide the checker
source IP or by itself prevent source-IP allowlisting.

Repository Bindings accepts only simple, exact PyPI pins and installs wheels
only; URLs, local paths, pip options, unpinned packages, and source builds are
rejected. Preparing this checker therefore requires PyPI access from the rsctf
process performing the trusted scan or admin approval.

The checker contract is identical for managed and BYOC services. rsctf points
`RSCTF_TARGET_IP` and `RSCTF_TARGET_PORT` at the current tunnel relay, while the
team's BYOC agent writes the expected flag to `/shared/flag`. The checker only
observes service behavior; it does not need to know which hosting mode is used.

For a local smoke test, start the service in one terminal:

```sh
printf '%s\n' 'rsctf{local_test}' >/tmp/rsctf-byoc-demo-flag
RSCTF_FLAG_FILE=/tmp/rsctf-byoc-demo-flag python3 src/app.py
```

Create an isolated checker environment and install the pinned wheel dependency:

```sh
python3 -m venv /tmp/rsctf-byoc-checker-venv
/tmp/rsctf-byoc-checker-venv/bin/python -m pip install \
  --disable-pip-version-check --no-input --only-binary=:all: \
  -- httpx==0.28.1
```

Then run the shuffled checker suite from the challenge directory:

```sh
RSCTF_ACTION=check \
RSCTF_TARGET_IP=127.0.0.1 \
RSCTF_TARGET_PORT=8080 \
RSCTF_ROUND=1 \
RSCTF_TEAM_ID=1 \
RSCTF_CHALLENGE_ID=1 \
RSCTF_FLAG='rsctf{local_test}' \
/tmp/rsctf-byoc-checker-venv/bin/python checker/run.py
echo $?
```

See the repository's `CHECKERS.md` before adapting this template.
