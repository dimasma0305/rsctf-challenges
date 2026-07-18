# Platform-hosted checker template

Copy this `checker/` directory beside an `AttackDefense` manifest. Repository
Bindings prepares `run.py` automatically; do not add a Dockerfile or
`requirements.txt`.

The example checker reads the current flag through the same `/flag` behavior an
attacker sees. rsctf has already written that round's value to the service's
`RSCTF_FLAG_FILE`, so the checker only needs to exercise player-visible service
behavior.

Start the service locally in one terminal:

```sh
printf '%s\n' 'rsctf{local_test}' >/tmp/rsctf-managed-demo-flag
RSCTF_FLAG_FILE=/tmp/rsctf-managed-demo-flag python3 src/app.py
```

Then run the checker from the challenge directory:

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
