# Self-hosted checker template

The checker contract is identical for managed and BYOC services. rsctf points
`RSCTF_TARGET_IP` and `RSCTF_TARGET_PORT` at the current tunnel relay, while the
team's BYOC agent writes the expected flag to `/shared/flag`. The checker only
observes service behavior; it does not need to know which hosting mode is used.

For a local smoke test, start the service in one terminal:

```sh
printf '%s\n' 'rsctf{local_test}' >/tmp/rsctf-byoc-demo-flag
RSCTF_FLAG_FILE=/tmp/rsctf-byoc-demo-flag python3 src/app.py
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

See the repository's `CHECKERS.md` before adapting this template.
