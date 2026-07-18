# Platform-hosted checker template

Copy this complete `checker/` directory beside an `AttackDefense` manifest.
Keep `lib.py` and `run.py` together: Repository Bindings detects the entry point
and prepares both files automatically. Do not add a Dockerfile or
`requirements.txt`; the template uses only Python's standard library.

`lib.py` owns only platform concerns: environment validation, `AdContext`,
verdict exceptions, exit-code mapping, and the `@ad_checker` wrapper. The demo's
HTTP imports and bounded `http_get` implementation live in `run.py` alongside
the service-specific assertions. For a raw TCP, binary, or custom TCP service,
replace that function with the protocol your challenge actually speaks; do not
add the protocol to `lib.py`. The decorator maps
`Mumble`/`Offline`/unexpected failures to exit codes and makes `check()` the
zero-argument entry point used at the bottom of the file.

The example checker reads the current flag through the same `/flag` behavior an
attacker sees. rsctf has already written that round's value to the service's
`RSCTF_FLAG_FILE`, so the checker only needs to exercise player-visible service
behavior.

Start the service locally in one terminal:

```sh
printf '%s\n' 'rsctf{local_test}' >/tmp/rsctf-managed-demo-flag
RSCTF_FLAG_FILE=/tmp/rsctf-managed-demo-flag python3 src/app.py
```

Then run the decorated checker from the challenge directory:

```sh
RSCTF_ACTION=check \
RSCTF_TARGET_IP=127.0.0.1 \
RSCTF_TARGET_PORT=8080 \
RSCTF_ROUND=1 \
RSCTF_TEAM_ID=1 \
RSCTF_CHALLENGE_ID=1 \
RSCTF_FLAG='rsctf{local_test}' \
python3 checker/run.py
echo $?
```

See the repository's `CHECKERS.md` for the complete environment, exit-code,
sandbox, and error-classification contract.
