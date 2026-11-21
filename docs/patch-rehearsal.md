# Rehearse hosted A&D patches

Generate a hidden event with five managed Python services. Teams fix one edge
case per service while its normal requests and rotating-flag checker stay
healthy. The fixtures cover order totals, guest lists, printed labels, page
counts and temperature readings. Each checker verifies a fresh HMAC of a
random nonce using the current flag. It never needs to retrieve the flag from
the service.

```sh
python3 tools/ad-patch-rehearsal/generate.py ../rsctf-rehearsal
rsctf challenge check --deny-warnings ../rsctf-rehearsal/repository
rsctf challenge matrix ../rsctf-rehearsal/repository
```

Import only `repository/` into a private staging game. Set a four-hour event
window, approve five teams with four accounts each, and keep the separate
`patches/` directory with the organizer. Each of its five folders contains:

| Archive | Use |
| --- | --- |
| `starter.zip` | Register as the team's original source. |
| `patched.zip` | Save and build the one-file fix. |
| `failed-build.zip` | Check that a failed build preserves the active service. |

The service Dockerfiles pin the same Python base by digest. For the offline
patch worker, supply that base as an approved Linux amd64 OCI archive and
select its manifest digest. The ZIP Dockerfiles reference it as
`rsctf-starter`. Their remaining instructions match the hosted image.

Run `python3 tools/ad-patch-rehearsal/test_rehearsal.py` for a short local
check of all five starters and repairs. Run
`python3 tools/ad-patch-rehearsal/test_docker.py` on a disposable Docker host
to start 25 containers concurrently and run 50 checker passes over two flag
rotations. CI runs the same five-team check. It also verifies that each
checker rejects another team's flag and its own previous-round flag.
The four-hour staging exercise also
needs the deployed platform, its runtimes, team VPN connections and scoring.
Record the actual elapsed time and measurements separately.
