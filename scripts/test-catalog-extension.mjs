#!/usr/bin/env node

/** Prove that authors may add packages without weakening the reference catalog. */

import { cpSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, dirname, join, relative, resolve, sep } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const temporary = mkdtempSync(join(tmpdir(), 'rsctf-catalog-extension-'))
const checkout = join(temporary, 'repository')

function includeSource(source) {
  const path = relative(ROOT, source)
  if (path === '') return true
  const topLevel = path.split(sep)[0]
  return !['.git', '.checker-venv', 'playtest'].includes(topLevel) && basename(source) !== '__pycache__'
}

try {
  cpSync(ROOT, checkout, { recursive: true, filter: includeSource })
  const packageRoot = join(checkout, 'challenges/Jeopardy/Misc/additional-static-handout')
  mkdirSync(join(packageRoot, 'dist'), { recursive: true })
  writeFileSync(
    join(packageRoot, 'challenge.yaml'),
    `name: Additional catalog fixture
author: rsctf test
description: Regression fixture proving that extra packages are allowed.
type: StaticAttachment
category: Misc
provide: dist
flags:
  - "rsctf{additional_catalog_fixture}"
`,
    'utf8',
  )
  writeFileSync(join(packageRoot, 'dist/readme.txt'), 'additional fixture\n', 'utf8')

  const result = spawnSync(process.execPath, ['scripts/validate.mjs'], {
    cwd: checkout,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
    timeout: 10_000,
  })
  if (result.error) throw result.error
  if (result.status !== 0) {
    throw new Error(`extended catalog validation failed:\n${result.stdout}${result.stderr}`)
  }
  console.log('OK: an additional challenge package passes catalog validation.')
} finally {
  rmSync(temporary, { recursive: true, force: true })
}
