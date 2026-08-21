#!/usr/bin/env node

import { readJsonStdin, requestJson, requiredEnvironment, serviceUrl } from './provenance-api.mjs'

async function main() {
  const base = serviceUrl('RSCTF_CONTROL_URL')
  const token = requiredEnvironment('RSCTF_SOLVE_RECEIPT_ISSUER_TOKEN')
  if (token.length < 32 || /\s/.test(token)) {
    throw new Error('RSCTF_SOLVE_RECEIPT_ISSUER_TOKEN must contain at least 32 non-whitespace characters')
  }
  const verifiedSolve = await readJsonStdin()
  const receipt = await requestJson(base, '/api/internal/event-security/solve-receipts', token, {
    method: 'POST',
    body: verifiedSolve,
  })
  if (typeof receipt?.proof !== 'string' || typeof receipt?.expiresAtUtc !== 'number') {
    throw new Error('receipt endpoint returned an invalid response')
  }
  process.stdout.write(`${JSON.stringify(receipt)}\n`)
}

main().catch((error) => {
  console.error(`issue solve receipt: ${error.message}`)
  process.exitCode = 1
})
