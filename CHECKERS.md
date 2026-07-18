# Checker development guide

Repository Bindings automatically prepares a Python checker found at
`checker/run.py` or `checker/src/run.py` beside an A&D/KotH manifest. It copies
the whole source directory, so keep the reusable `lib.py` beside `run.py` and
copy both files when starting a checker.

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

Any other code is also `InternalError`. The decorators in the bundled `lib.py`
load and validate this environment and map checker outcomes to these codes:

- returning normally is OK;
- raising `Mumble` means the target answered incorrectly;
- raising `Offline` means the target could not complete the request;
- configuration errors and unexpected exceptions are InternalError.

This mapping matters because an ordinary uncaught Python exception exits with
code `1` and would otherwise incorrectly blame the team as Mumble.

## Template structure

Keep framework concerns in the dependency-free `lib.py` and service assertions
in the small `run.py`. For A&D, import the shared helpers and decorate one
function:

```python
from lib import AdContext, ad_checker, expect_text


@ad_checker
def check(context: AdContext) -> None:
    expect_text(context, "/health", "ok")
    expect_text(context, "/flag", context.flag)


if __name__ == "__main__":
    raise SystemExit(check())
```

`@ad_checker` turns the decorated function into a zero-argument entry point. It
creates an `AdContext` from `RSCTF_*`, catches the documented exceptions, and
returns the correct rsctf exit code. `expect_text` makes a bounded HTTP request
to the supplied target and requires an exact response. For a structured or
custom protocol check, use `get_text` and raise `Mumble` when parsing or
validation fails.

KotH uses the matching context and decorator, without a flag assertion:

```python
from lib import KothContext, expect_text, koth_checker


@koth_checker
def check(context: KothContext) -> None:
    expect_text(context, "/health", "ok")


if __name__ == "__main__":
    raise SystemExit(check())
```

Copy the complete `checker/` directory from the closest example, then edit only
the challenge-specific assertions in `run.py`. Keep `lib.py` and `run.py`
together; do not copy only the entry point.

## Sandbox rules

- Use the Python standard library. The bundled `lib.py` has no external
  dependencies; `requirements.txt` is rejected and pip is never run during
  import.
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

Each example checker directory includes both `lib.py` and `run.py`, plus exact
commands for starting its service and running the decorated entry point. Before
pushing, also run:

```sh
node scripts/validate.mjs
python3 -m compileall -q AD Koth Jeopardy scripts
python3 scripts/test-checkers.py
```

CI performs these checks, exercises all four checker verdict classes, and
builds every bundled service context.
