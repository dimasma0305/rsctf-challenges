# Platform-hosted checker template

Copy this complete `checker/` directory beside an `AttackDefense` manifest.
Keep `lib.py` and `run.py` together: Repository Bindings detects the entry point
and prepares both files automatically. This template also pins its one external
checker dependency in `requirements.txt`; keep the pin exact so imports remain
reviewable.

`lib.py` owns only platform concerns: environment validation, `AdContext`,
verdict exceptions, exit-code mapping, `@checker`, and `run_ad_checker()`. The
legacy single-function `@ad_checker` wrapper remains available. This Pwn demo's
bounded raw TCP exchange uses `pwntools==4.15.0` inside `run.py`. Its
`tcp_request` helper opens one tube per newline-framed command with quiet
logging and a fixed timeout. Two `@checker` functions validate `PING` → `PONG`
and `GET_FLAG` → the current flag as separate focused checks.

`run_ad_checker()` cryptographically shuffles the registry and attempts every
function once. The complete suite, rather than every individual function, must
cover service health and the current flag. Checks must be read-only and cannot
depend on another check running first. After all checks are attempted, failures
are combined with deterministic priority: InternalError, Offline, Mumble, then
OK. For a binary or custom TCP service, replace `tcp_request` and the whole
suite with the protocol your challenge actually speaks. Do not add the protocol
to `lib.py`. Sequence variation is defense-in-depth against checker
fingerprinting, but it does not hide the checker source IP or by itself defeat
source-IP allowlisting.

The example checker reads the current flag through the same `GET_FLAG` command
an attacker sees. rsctf has already written that round's value to the service's
`RSCTF_FLAG_FILE`, so the checker only needs to exercise player-visible service
behavior. Repository Bindings installs the pinned checker requirements before
running `run.py`. It accepts only simple, exact PyPI pins and installs wheels
only; URLs, local paths, pip options, unpinned packages, and source builds are
rejected. Preparing this checker therefore requires PyPI access from the rsctf
process performing the trusted scan or admin approval.

Start the service locally in one terminal:

```sh
printf '%s\n' 'rsctf{local_test}' >/tmp/rsctf-managed-demo-flag
RSCTF_FLAG_FILE=/tmp/rsctf-managed-demo-flag python3 src/app.py
```

Create an isolated checker environment and install the pinned wheel dependency:

```sh
python3 -m venv /tmp/rsctf-checker-venv
/tmp/rsctf-checker-venv/bin/python -m pip install \
  --disable-pip-version-check --no-input --only-binary=:all: \
  -- pwntools==4.15.0
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
/tmp/rsctf-checker-venv/bin/python checker/run.py
echo $?
```

See the repository's `CHECKERS.md` for the complete environment, exit-code,
sandbox, and error-classification contract.
