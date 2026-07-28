# API arena King-of-the-Hill checker

Copy both `lib.py` and `run.py`. The checker is dependency-free and verifies
only the player-visible health, banner, and bounded evidence-feed contract. It
never reads or changes a team's score.

For this challenge, RSCTF samples the latest signed multi-team snapshot before
and after running the checker. Only an unchanged snapshot around a healthy
functional probe can become score evidence. There is no current king,
provisional capture, or champion cooldown in API mode. The checker receives no
referee secret, player capability, or `RSCTF_FLAG`; its exit-code contract is
still `0` OK, `1` Mumble, `2` Offline, and `3` InternalError.

Start `src/app.py`, then run:

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

The independent referee is documented in [`../observer/README.md`](../observer/README.md).
