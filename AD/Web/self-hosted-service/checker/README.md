# Self-hosted checker template

Copy both `lib.py` and `run.py`; they form one dependency-free checker template.
`lib.py` provides the protocol-neutral `AdContext`, verdict exceptions, and
`@ad_checker`. This demo's bounded HTTP request code and service assertions live
in `run.py`. Replace its `http_get` function when your service uses raw TCP,
binary framing, or another custom TCP protocol; the decorator still validates
`RSCTF_*` and maps outcomes to rsctf exit codes. Do not add `requirements.txt`
or external packages.

The checker contract is identical for managed and BYOC services. rsctf points
`RSCTF_TARGET_IP` and `RSCTF_TARGET_PORT` at the current tunnel relay, while the
team's BYOC agent writes the expected flag to `/shared/flag`. The checker only
observes service behavior; it does not need to know which hosting mode is used.

For a local smoke test, start the service in one terminal:

```sh
printf '%s\n' 'rsctf{local_test}' >/tmp/rsctf-byoc-demo-flag
RSCTF_FLAG_FILE=/tmp/rsctf-byoc-demo-flag python3 src/app.py
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

See the repository's `CHECKERS.md` before adapting this template.
