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
| `patched-v2.zip` | Apply a second fix that also accepts JSON `null`. |
| `failed-build.zip` | Check that a failed build preserves the active service. |

To verify both rollback choices on the deployed platform, activate the two
repairs in order. On revision two, posting JSON `null` to `/evaluate`
returns HTTP 200. After rollback to the previous revision, the same input
returns HTTP 400 and the first fix still works. After rollback to the starter,
the original edge case fails again. For example, an empty order returns
`0` on either repair and `null` on the starter. Check through the same team
endpoint after each change.

Before activating a revision, record the 32-character response from
`GET /installation` on each team endpoint. The service stores this identifier
in SQLite under `/var/lib/rehearsal`. Each team and challenge should have a
different value. Read it again after activation, a failed build, and each
rollback. Any change means the replacement lost the team's data. On Docker,
the image creates a separate volume for this directory on each fresh service.
To preserve it across replacements, attach the same team's data volume to
the replacement. Deliver its current flag separately.

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

### Check Kubernetes storage

On a disposable Docker host with Kind v0.32.0 and kubectl, run
`python3 tools/ad-patch-rehearsal/test_kubernetes.py`. It creates a temporary
single-node cluster with its own kubeconfig. The order-total fixture loses
its SQLite installation ID when a replacement Pod starts without a claim.
The test then gives each of two teams a separate claim and checks the ID,
Service address, flag and application behavior across two repairs, rollback
to the previous repair and rollback to the starter. This exercises Kubernetes
storage directly. Player activation through RSCTF needs its own runtime test.
