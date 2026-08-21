# Deterministic variant generator

rsctf starts this image twice with networking disabled, a read-only root
filesystem, and bounded CPU, memory, process count, output size, and runtime.
Both executions must produce byte-identical stdout before rsctf freezes the
variant.

The image reads one URL-safe, unpadded base64 JSON object from
`RSCTF_VARIANT_INPUT`:

```json
{
  "gameId": 7,
  "challengeId": 11,
  "participationId": 23,
  "revision": 1,
  "seed": "base64url-encoded-32-byte-seed"
}
```

It writes one compact JSON object to stdout:

```json
{
  "manifest": {
    "flag": "rsctf{sum_10485}",
    "content": "Player-facing Markdown",
    "hints": ["Player-facing hint"]
  },
  "artifactSha256": "sha256-of-the-compact-canonical-manifest-without-a-prefix"
}
```

Diagnostics go to stderr. Never write the seed, secrets, or extra text to
stdout. `scripts/test-provenance.py` exercises the exact contract without
requiring Docker.
