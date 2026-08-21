#!/usr/bin/env node

import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { createServer } from 'node:http'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

async function runScript(name, env, stdin = '') {
  const child = spawn(process.execPath, [resolve(ROOT, 'scripts', name)], {
    cwd: ROOT,
    env,
    stdio: ['pipe', 'pipe', 'pipe'],
  })
  const stdout = []
  const stderr = []
  child.stdout.on('data', (chunk) => stdout.push(chunk))
  child.stderr.on('data', (chunk) => stderr.push(chunk))
  child.stdin.end(stdin)
  const [code] = await once(child, 'close')
  const output = Buffer.concat(stdout).toString('utf8')
  const errors = Buffer.concat(stderr).toString('utf8')
  assert.equal(code, 0, `${name} failed:\n${errors}`)
  return JSON.parse(output)
}

async function requestBody(request) {
  const chunks = []
  for await (const chunk of request) chunks.push(chunk)
  const raw = Buffer.concat(chunks).toString('utf8')
  return raw === '' ? undefined : JSON.parse(raw)
}

async function main() {
  const requests = []
  const server = createServer(async (request, response) => {
    const body = await requestBody(request)
    requests.push({
      method: request.method,
      url: request.url,
      authorization: request.headers.authorization,
      body,
    })

    response.setHeader('Content-Type', 'application/json')
    if (request.method === 'POST' && request.url === '/api/edit/games/42/variants/generate') {
      response.end(JSON.stringify({ generated: 2 }))
    } else if (request.method === 'GET' && request.url === '/api/edit/games/42/variants') {
      response.end(
        JSON.stringify([
          { challengeId: 17, participationId: 93, revision: 1 },
          { challengeId: 17, participationId: 94, revision: 1 },
        ])
      )
    } else if (
      request.method === 'POST' &&
      request.url === '/api/internal/event-security/solve-receipts'
    ) {
      response.end(JSON.stringify({ proof: 'signed.example.proof', expiresAtUtc: 1_900_000_000_000 }))
    } else {
      response.statusCode = 404
      response.end(JSON.stringify({ title: 'not found', status: 404 }))
    }
  })

  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  const address = server.address()
  assert(address && typeof address !== 'string')
  const origin = `http://127.0.0.1:${address.port}`

  try {
    const variants = await runScript('generate-variants.mjs', {
      RSCTF_URL: origin,
      RSCTF_GAME_ID: '42',
      RSCTF_ADMIN_TOKEN: 'admin-test-token',
      RSCTF_EXPECTED_VARIANTS: '2',
    })
    assert.deepEqual(
      { gameId: variants.gameId, generated: variants.generated, frozen: variants.frozen },
      { gameId: 42, generated: 2, frozen: 2 }
    )
    assert.equal(variants.expected, 2)

    const verifiedSolve = {
      gameId: 42,
      challengeId: 17,
      participationId: 93,
      userId: null,
      variantId: '018f3c6a-d79b-7cc0-8f68-8fdbad0f57bb',
      answer: 'rsctf{sum_10485}',
      issuerIdentity: 'example-verifier-v1',
    }
    const receipt = await runScript(
      'issue-solve-receipt.mjs',
      {
        RSCTF_CONTROL_URL: origin,
        RSCTF_SOLVE_RECEIPT_ISSUER_TOKEN: 'machine-receipt-token-32-characters',
      },
      JSON.stringify(verifiedSolve)
    )
    assert.equal(receipt.proof, 'signed.example.proof')

    assert.deepEqual(requests, [
      {
        method: 'POST',
        url: '/api/edit/games/42/variants/generate',
        authorization: 'Bearer admin-test-token',
        body: undefined,
      },
      {
        method: 'GET',
        url: '/api/edit/games/42/variants',
        authorization: 'Bearer admin-test-token',
        body: undefined,
      },
      {
        method: 'POST',
        url: '/api/internal/event-security/solve-receipts',
        authorization: 'Bearer machine-receipt-token-32-characters',
        body: verifiedSolve,
      },
    ])
  } finally {
    await new Promise((resolveClose) => server.close(resolveClose))
  }

  console.log('OK: provenance automation clients use the documented endpoints and credentials.')
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
