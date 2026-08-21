#!/usr/bin/env node

import {
  optionalNonNegativeIntegerEnvironment,
  positiveIntegerEnvironment,
  requestJson,
  requiredEnvironment,
  serviceUrl,
} from './provenance-api.mjs'

async function main() {
  const base = serviceUrl('RSCTF_URL')
  const gameId = positiveIntegerEnvironment('RSCTF_GAME_ID')
  const expected = optionalNonNegativeIntegerEnvironment('RSCTF_EXPECTED_VARIANTS')
  const token = requiredEnvironment('RSCTF_ADMIN_TOKEN')

  const generated = await requestJson(base, `/api/edit/games/${gameId}/variants/generate`, token, {
    method: 'POST',
  })
  if (!Number.isSafeInteger(generated?.generated) || generated.generated < 0) {
    throw new Error('variant-generation response has no valid generated count')
  }
  const variants = await requestJson(base, `/api/edit/games/${gameId}/variants`, token)
  if (!Array.isArray(variants)) throw new Error('variant-list response is not an array')
  if (expected !== undefined && variants.length !== expected) {
    throw new Error(`expected ${expected} frozen variants, received ${variants.length}`)
  }

  process.stdout.write(
    `${JSON.stringify(
      {
        gameId,
        generated: generated.generated,
        frozen: variants.length,
        expected,
        variants,
      },
      null,
      2
    )}\n`
  )
}

main().catch((error) => {
  console.error(`generate variants: ${error.message}`)
  process.exitCode = 1
})
