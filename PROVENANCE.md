# Challenge provenance automation

The `Jeopardy/Misc/deterministic-variant` package is a complete example of the
part of challenge provenance that rsctf can run by itself: deterministic
per-participation content, hints, and flags. Solve receipts are documented
separately because they require an organizer-operated verifier and are disabled
in the runnable manifest.

## What Repository Bindings imports

The challenge manifest owns these fields:

```yaml
variantMode: PerParticipation
variantGeneratorImage: "docker.io/dimasmaualana/rsctf-provenance-generator@sha256:6efc8c4382c993cf0a5469d16cc3e152476440c476df76fbaaf99d02bd82dc79"
variantGeneratorDigest: "sha256:6efc8c4382c993cf0a5469d16cc3e152476440c476df76fbaaf99d02bd82dc79"
solveReceiptMode: Disabled
```

The image and digest must be changed together. A mutable tag such as `:main`
is invalid. Repository rescans may change this policy only before the event
starts. Normal manifests that omit every provenance key preserve any policy an
organizer configured in Admin.

The checked-in generator source reads `RSCTF_VARIANT_INPUT` and emits one JSON
manifest. rsctf runs it twice with the same input in a network-disabled,
read-only, resource-limited container. Only byte-identical output is frozen.
The player receives generated `content` and `hints`; the generated `flag` stays
server-side for grading.

Run the contract test locally:

```sh
python3 scripts/test-provenance.py
docker build -t rsctf-provenance-generator:test \
  Jeopardy/Misc/deterministic-variant/generator
```

## Publish a changed generator

The example manifest references a public multi-architecture image built from
the checked-in source. For your own generator, publish a reviewed image first:

```sh
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --provenance=mode=max --sbom=true --push \
  -t REGISTRY/ORGANIZATION/GENERATOR:REVISION \
  Jeopardy/Misc/deterministic-variant/generator
```

Copy the resulting manifest-list digest into both YAML fields, commit that
change, and let Repository Bindings rescan it. Do not have CI rewrite a live
event's digest automatically: publishing and selecting the reviewed immutable
image are deliberately separate approvals.

The trusted Docker daemon used by rsctf's control role must already contain the
exact image because the generator checks the local immutable identity and does
not pull during a generation request:

```sh
docker pull 'REGISTRY/ORGANIZATION/GENERATOR@sha256:DIGEST'
```

## Generate and freeze variants

Configure the rsctf deployment with a stable secret before importing an enabled
variant policy:

```text
RSCTF_EVENT_VPN_CREDENTIAL_KEY=<at-least-32-non-whitespace-characters>
```

The same key derives deterministic seeds across restarts. Rotating it after
variants have been frozen does not rewrite their immutable records, but it
changes any future generation and therefore requires an explicit event plan.

Accept the event's teams before generating variants. Then run the package-free
automation client with an administrator JWT kept in the automation secret
store:

```sh
RSCTF_URL=https://ctf.example \
RSCTF_GAME_ID=42 \
RSCTF_EXPECTED_VARIANTS=24 \
RSCTF_ADMIN_TOKEN='ADMIN_JWT' \
node scripts/generate-variants.mjs
```

The script calls:

1. `POST /api/edit/games/42/variants/generate`
2. `GET /api/edit/games/42/variants`

Generation is idempotent: it creates only missing frozen variants. Run it again
for teams accepted later, still before the start time. Set
`RSCTF_EXPECTED_VARIANTS` to the accepted/suspended participation count times
the enabled `PerParticipation` challenge count; the client fails if the frozen
inventory does not match. After the event starts, generation and policy changes
are rejected.

## Optional trusted solve receipts

Receipts are not an exploit uploader or an organizer solver. Enable them only
after deploying a verifier that independently checks a meaningful player action.
Before the event starts, change the challenge manifest to:

```yaml
solveReceiptMode: Required
receiptVerifierIdentity: "example-verifier-v1"
```

Configure the control deployment and the verifier's secret store with the same
independent machine credential:

```text
RSCTF_SOLVE_RECEIPT_ISSUER_TOKEN=<at-least-32-non-whitespace-characters>
```

After the verifier has authenticated the player and confirmed the solve, it can
pipe this request into the included adapter:

```sh
printf '%s\n' '{
  "gameId": 42,
  "challengeId": 17,
  "participationId": 93,
  "userId": null,
  "variantId": "018f3c6a-d79b-7cc0-8f68-8fdbad0f57bb",
  "answer": "rsctf{sum_10485}",
  "issuerIdentity": "example-verifier-v1"
}' | \
RSCTF_CONTROL_URL=https://control.internal.example \
RSCTF_SOLVE_RECEIPT_ISSUER_TOKEN='MACHINE_SECRET' \
node scripts/issue-solve-receipt.mjs
```

For a challenge without generated variants, send `"variantId": null`. For a
generated challenge, use the canonical variant ID exposed in that participant's
challenge details; rsctf rejects any mismatch. The adapter calls the protected
control-only endpoint and prints the short-lived proof that the verifier returns
to the player. The player submits that proof alongside the exact answer. rsctf
binds it to the game, challenge, participation, optional user, canonical variant,
answer hash, issuer, and expiry, then consumes it in the grading transaction.

`scripts/issue-solve-receipt.mjs` is intentionally only an authenticated API
adapter. Do not expose it directly to players and do not treat receipt issuance
as verification. The verifier must derive participation identity from trusted
authentication rather than trusting player-supplied IDs, and arbitrary player
code must run only in a separate hardened judge.
