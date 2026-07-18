# Checker development guide

Repository Bindings automatically prepares a Python checker found at
`checker/run.py` or `checker/src/run.py` beside an A&D/KotH manifest.

These checked-in examples are intended to be copied:

- [`AD/Pwn/attack-defense-service/checker/`](AD/Pwn/attack-defense-service/checker/)
  verifies a platform-hosted service and its rotating flag.
- [`AD/Web/self-hosted-service/checker/`](AD/Web/self-hosted-service/checker/)
  verifies the same contract through a BYOC tunnel.
- [`Koth/Pwn/king-of-the-hill/checker/`](Koth/Pwn/king-of-the-hill/checker/)
  checks hill health without touching the KotH ownership marker.

## Runtime contract

rsctf runs the prepared checker as Python with no command-line arguments. The
host environment is cleared; these are the supported checker-contract values
(the sandbox also supplies its private `HOME` and `TMPDIR`):

| Variable | A&D | KotH | Meaning |
| --- | --- | --- | --- |
| `RSCTF_ACTION` | `check` | `check` | Reserved action selector |
| `RSCTF_TARGET_IP` | yes | yes | Resolved numeric target address |
| `RSCTF_TARGET_PORT` | yes | yes | Target port from `container.exposePort` |
| `RSCTF_ROUND` | yes | yes | Current round number |
| `RSCTF_TEAM_ID` | participation ID | `0` | Historical name; A&D receives the participation ID |
| `RSCTF_CHALLENGE_ID` | yes | yes | Imported challenge ID |
| `RSCTF_FLAG` | yes | absent | Expected rotating flag for this A&D service |

The process exit code is the entire result:

| Code | Verdict | Use it when |
| ---: | --- | --- |
| `0` | OK | The service is reachable and functionally correct |
| `1` | Mumble | It answered, but its protocol or content is wrong |
| `2` | Offline | Connection, reset, or request timeout prevented a response |
| `3` | InternalError | Checker configuration or checker code is broken |

Any other code is also `InternalError`. An uncaught Python exception normally
exits with code `1`, which would incorrectly blame the team as Mumble. Keep the
top-level exception mapping shown in the templates.

## Sandbox rules

- Use the Python standard library. `requirements.txt` is rejected and pip is
  never run during import.
- Set a short request timeout. The checker has one outer deadline, and an outer
  timeout becomes Offline.
- Network access is confined to exactly the supplied target IP and port. Do not
  follow redirects or call a database, DNS API, peer service, or second port.
- The checker source and venv are read-only. `HOME` and `TMPDIR` point to a small
  temporary writable directory.
- Do not shell out to `curl` or other binaries. The sandbox does not provide a
  dependable `PATH` and blocks general subprocess execution.
- stdout and stderr are discarded. Do not print flags; return the correct exit
  code instead.
- Resolve bundled data relative to `Path(__file__).resolve().parent`, because
  the working directory is not guaranteed to be the checker directory.

## Flag delivery

The platform delivers the flag before running the checker:

- Managed A&D writes it inside the service container at `RSCTF_FLAG_FILE`.
- Self-hosted A&D sends it through the BYOC relay, whose agent writes the shared
  `/shared/flag` file.
- The checker receives the same expected value as `RSCTF_FLAG`.

Service code must read its flag file at request time. A creation-time environment
value cannot rotate. The checker must not replace the flag itself, because that
would bypass the platform's delivery path.

KotH is different: it has no flag environment. rsctf reads `/koth/king` before
and after the custom checker and performs ownership attribution itself. A KotH
checker should verify a normal health/functionality endpoint without reading or
modifying that marker.

Keep a prepared checker beside every enabled A&D and KotH challenge. The TCP
fallback can diagnose a missing checker, but official epoch scoring does not
start until every enabled engine challenge has a prepared checker.

## Local workflow

Each example checker directory includes exact commands for starting its service
and running `run.py`. Before pushing, also run:

```sh
node scripts/validate.mjs
python3 -m compileall -q AD Koth Jeopardy scripts
python3 scripts/test-checkers.py
```

CI performs these checks, exercises all four checker verdict classes, and
builds every bundled service context.
