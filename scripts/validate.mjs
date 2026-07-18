#!/usr/bin/env node

/**
 * Package-free validator for the rsctf repository-binding example.
 *
 * This intentionally implements only the small, readable YAML subset used by
 * this example. Keeping it local avoids an npm install in CI while still making
 * indentation, duplicate keys, known fields, paths, local build contexts, and
 * checker layout fail closed. rsctf remains the authoritative importer schema.
 */

import {
  existsSync,
  lstatSync,
  readFileSync,
  readdirSync,
} from 'node:fs'
import { dirname, isAbsolute, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const errors = []
const notices = []
const checkerLibraries = []

const EVENT_KEYS = new Set([
  'title',
  'start',
  'end',
  'poster',
  'hidden',
  'summary',
  'content',
  'acceptWithoutReview',
  'inviteCode',
  'organizations',
  'teamMemberCountLimit',
  'containerCountLimit',
  'practiceMode',
  'writeupRequired',
  'writeupDeadline',
  'writeupNote',
  'bloodBonus',
  'ad',
])

const EVENT_AD_KEYS = new Set([
  'tickSeconds',
  'flagLifetimeTicks',
  'warmupSeconds',
  'resetCooldownMinutes',
  'allowSnapshotDownload',
  'snapshotRetentionDays',
  'getflagWindowFraction',
  'minGracePeriodSeconds',
])

const CHALLENGE_KEYS = new Set([
  'name',
  'author',
  'description',
  'type',
  'category',
  'minScoreRate',
  'difficulty',
  'ignore',
  'hints',
  'flags',
  'flagTemplate',
  'provide',
  'disableBloodBonus',
  'submissionLimit',
  'container',
  'ad',
])

const CONTAINER_KEYS = new Set([
  'containerImage',
  'flagTemplate',
  'memoryLimit',
  'cpuCount',
  'storageLimit',
  'exposePort',
  'enableTrafficCapture',
  'enableSharedContainer',
])

const AD_KEYS = new Set([
  'checkerImage',
  'allowEgress',
  'allowSelfReset',
  'sshRequiresFlag',
  'selfHosted',
])

const TYPES = [
  'StaticAttachment',
  'DynamicAttachment',
  'StaticContainer',
  'DynamicContainer',
  'AttackDefense',
  'KingOfTheHill',
]

const EXPECTED_TYPE_COUNTS = new Map(
  TYPES.map((type) => [type, type === 'AttackDefense' ? 2 : 1]),
)

const EXPECTED_CHALLENGE_COUNT = [...EXPECTED_TYPE_COUNTS.values()]
  .reduce((total, count) => total + count, 0)

const CATEGORIES = new Set([
  'Misc',
  'Crypto',
  'Pwn',
  'Web',
  'Reverse',
  'Blockchain',
  'Forensics',
  'Hardware',
  'Mobile',
  'PPC',
  'AI',
  'Pentest',
  'OSINT',
])

const CONTAINER_TYPES = new Set([
  'StaticContainer',
  'DynamicContainer',
  'AttackDefense',
  'KingOfTheHill',
])

function reportError(file, message) {
  errors.push(`${relative(ROOT, file) || '.'}: ${message}`)
}

function walk(root) {
  const files = []
  const stack = [root]
  while (stack.length > 0) {
    const current = stack.pop()
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const target = resolve(current, entry.name)
      if (entry.isDirectory() && (entry.name === '.git' || entry.name === '__pycache__')) {
        continue
      }
      if (entry.isSymbolicLink()) {
        files.push(target)
      } else if (entry.isDirectory()) {
        stack.push(target)
      } else if (entry.isFile()) {
        files.push(target)
      }
    }
  }
  return files.sort()
}

function indentation(line, file, lineNumber) {
  if (line.includes('\t')) {
    throw new Error(`${file}:${lineNumber}: tabs are not allowed in YAML indentation`)
  }
  return line.length - line.trimStart().length
}

function parseScalar(raw, file, lineNumber) {
  const value = raw.trim()
  if (value === '') return null
  if (value.startsWith('"')) {
    try {
      return JSON.parse(value)
    } catch (error) {
      throw new Error(`${file}:${lineNumber}: invalid quoted string (${error.message})`)
    }
  }
  if (value.startsWith("'")) {
    if (!value.endsWith("'") || value.length < 2) {
      throw new Error(`${file}:${lineNumber}: unterminated single-quoted string`)
    }
    return value.slice(1, -1).replaceAll("''", "'")
  }
  if (value === 'true') return true
  if (value === 'false') return false
  if (value === 'null' || value === '~') return null
  if (/^-?(?:0|[1-9]\d*)$/.test(value)) return Number.parseInt(value, 10)
  if (/^-?(?:0|[1-9]\d*)\.\d+$/.test(value)) return Number.parseFloat(value)
  if (/[[\]{}&,*!>|%@`]/.test(value)) {
    throw new Error(`${file}:${lineNumber}: unsupported YAML syntax in ${JSON.stringify(value)}`)
  }
  return value
}

function parseYaml(text, file) {
  const lines = text.replaceAll('\r\n', '\n').split('\n')

  const nextContent = (start) => {
    for (let index = start; index < lines.length; index += 1) {
      const trimmed = lines[index].trim()
      if (trimmed !== '' && !trimmed.startsWith('#')) return index
    }
    return lines.length
  }

  const parseSequence = (start, expectedIndent) => {
    const values = []
    let index = start
    while (index < lines.length) {
      const contentIndex = nextContent(index)
      if (contentIndex >= lines.length) return [values, lines.length]
      const line = lines[contentIndex]
      const actualIndent = indentation(line, file, contentIndex + 1)
      if (actualIndent < expectedIndent) return [values, contentIndex]
      if (actualIndent > expectedIndent) {
        throw new Error(`${file}:${contentIndex + 1}: unexpected indentation`)
      }
      const trimmed = line.trim()
      if (!trimmed.startsWith('- ')) return [values, contentIndex]
      const raw = trimmed.slice(2).trim()
      if (raw === '') {
        throw new Error(`${file}:${contentIndex + 1}: nested sequence items are not used here`)
      }
      values.push(parseScalar(raw, file, contentIndex + 1))
      index = contentIndex + 1
    }
    return [values, index]
  }

  const parseMapping = (start, expectedIndent) => {
    const value = Object.create(null)
    let index = start
    while (index < lines.length) {
      const contentIndex = nextContent(index)
      if (contentIndex >= lines.length) return [value, lines.length]
      const line = lines[contentIndex]
      const actualIndent = indentation(line, file, contentIndex + 1)
      if (actualIndent < expectedIndent) return [value, contentIndex]
      if (actualIndent > expectedIndent) {
        throw new Error(`${file}:${contentIndex + 1}: unexpected indentation`)
      }
      const trimmed = line.trim()
      if (trimmed.startsWith('- ')) return [value, contentIndex]
      const match = /^([A-Za-z][A-Za-z0-9]*):(?:\s*(.*))?$/.exec(trimmed)
      if (!match) {
        throw new Error(`${file}:${contentIndex + 1}: expected key: value`)
      }
      const [, key, raw = ''] = match
      if (Object.hasOwn(value, key)) {
        throw new Error(`${file}:${contentIndex + 1}: duplicate key ${key}`)
      }

      if (raw === '|' || raw === '|-') {
        const blockLines = []
        let cursor = contentIndex + 1
        let blockIndent = null
        while (cursor < lines.length) {
          const candidate = lines[cursor]
          const candidateIndent = indentation(candidate, file, cursor + 1)
          if (candidate.trim() !== '' && candidateIndent <= expectedIndent) break
          if (candidate.trim() !== '' && blockIndent === null) blockIndent = candidateIndent
          if (candidate.trim() === '') {
            blockLines.push('')
          } else {
            if (candidateIndent < blockIndent) {
              throw new Error(`${file}:${cursor + 1}: malformed block scalar indentation`)
            }
            blockLines.push(candidate.slice(blockIndent))
          }
          cursor += 1
        }
        value[key] = blockLines.join('\n') + (raw === '|' ? '\n' : '')
        index = cursor
        continue
      }

      if (raw !== '') {
        value[key] = parseScalar(raw, file, contentIndex + 1)
        index = contentIndex + 1
        continue
      }

      const childIndex = nextContent(contentIndex + 1)
      if (childIndex >= lines.length) {
        value[key] = null
        return [value, lines.length]
      }
      const childIndent = indentation(lines[childIndex], file, childIndex + 1)
      if (childIndent <= expectedIndent) {
        value[key] = null
        index = childIndex
        continue
      }
      if (childIndent !== expectedIndent + 2) {
        throw new Error(`${file}:${childIndex + 1}: nested keys must use two spaces`)
      }
      const parsed = lines[childIndex].trim().startsWith('- ')
        ? parseSequence(childIndex, childIndent)
        : parseMapping(childIndex, childIndent)
      value[key] = parsed[0]
      index = parsed[1]
    }
    return [value, index]
  }

  const first = nextContent(0)
  if (first >= lines.length) throw new Error(`${file}: empty YAML document`)
  if (indentation(lines[first], file, first + 1) !== 0) {
    throw new Error(`${file}:${first + 1}: top-level keys must not be indented`)
  }
  const [document, end] = parseMapping(first, 0)
  if (nextContent(end) < lines.length) {
    throw new Error(`${file}:${nextContent(end) + 1}: trailing YAML content`)
  }
  return document
}

function parseFile(file) {
  try {
    return parseYaml(readFileSync(file, 'utf8'), relative(ROOT, file))
  } catch (error) {
    reportError(file, error.message)
    return null
  }
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function checkKnownKeys(value, known, file, label) {
  if (!isRecord(value)) {
    reportError(file, `${label} must be a mapping`)
    return false
  }
  for (const key of Object.keys(value)) {
    if (!known.has(key)) reportError(file, `unknown ${label} key: ${key}`)
  }
  return true
}

function positiveInteger(value) {
  return Number.isInteger(value) && value > 0
}

function checkChallengeLayout(file, model) {
  const parts = relative(ROOT, file).split(sep)
  const expectedMode = model.type === 'AttackDefense'
    ? 'AD'
    : model.type === 'KingOfTheHill'
      ? 'Koth'
      : 'Jeopardy'
  if (
    parts.length !== 4
    || parts[0] !== expectedMode
    || parts[1] !== model.category
    || parts[2].trim() === ''
    || !['challenge.yaml', 'challenge.yml'].includes(parts[3])
  ) {
    reportError(
      file,
      `must use ${expectedMode}/<category>/<challenge>/challenge.yaml and match category ${model.category}`,
    )
  }
}

function checkSafeProvide(file, provided) {
  if (typeof provided !== 'string' || provided.trim() === '') {
    reportError(file, 'provide must be a non-empty relative path')
    return
  }
  if (isAbsolute(provided) || provided.includes('\\')) {
    reportError(file, `unsafe provide path: ${provided}`)
    return
  }
  const components = provided.split('/')
  if (components.some((part) => part === '..' || part === '' || part === '.')) {
    reportError(file, `unsafe provide path: ${provided}`)
    return
  }
  const packageRoot = dirname(file)
  const target = resolve(packageRoot, provided)
  if (target !== packageRoot && !target.startsWith(`${packageRoot}${sep}`)) {
    reportError(file, `provide escapes its challenge directory: ${provided}`)
    return
  }
  if (!existsSync(target)) {
    reportError(file, `provide path does not exist: ${provided}`)
    return
  }
  const targets = lstatSync(target).isDirectory() ? walk(target) : [target]
  for (const candidate of targets) {
    if (lstatSync(candidate).isSymbolicLink()) {
      reportError(file, `provide contains a symbolic link: ${relative(packageRoot, candidate)}`)
    }
  }
}

function checkChecker(file, model) {
  const packageRoot = dirname(file)
  const checkerRoot = resolve(packageRoot, 'checker')
  const hasChecker = existsSync(checkerRoot)
  const checkerImage = model.ad?.checkerImage

  if (model.type === 'AttackDefense' && typeof model.ad?.selfHosted !== 'boolean') {
    reportError(file, 'AttackDefense example must explicitly set ad.selfHosted to true or false')
  }

  if (!hasChecker) {
    if (model.type === 'AttackDefense' || model.type === 'KingOfTheHill') {
      reportError(file, `${model.type} example must include checker/run.py`)
    }
    return
  }

  const checkerFiles = walk(checkerRoot)
  if (checkerFiles.some((candidate) => candidate.endsWith(`${sep}requirements.txt`))) {
    reportError(file, 'checker requirements.txt is forbidden by the current importer')
  }
  const entry = resolve(checkerRoot, 'run.py')
  if (!existsSync(entry)) {
    reportError(file, 'checker must provide checker/run.py')
    return
  }
  const library = resolve(checkerRoot, 'lib.py')
  if (!existsSync(library)) {
    reportError(file, 'checker must provide checker/lib.py beside run.py')
    return
  }
  const readme = resolve(checkerRoot, 'README.md')
  if (!existsSync(readme) || readFileSync(readme, 'utf8').trim() === '') {
    reportError(file, 'checker must include a non-empty checker/README.md')
  }
  const source = readFileSync(entry, 'utf8')
  const librarySource = readFileSync(library, 'utf8')
  checkerLibraries.push({ file: library, source: librarySource })
  if (!source.includes('from lib import')) {
    reportError(file, 'checker/run.py must import reusable helpers from sibling lib.py')
  }
  if (!source.includes('raise SystemExit(check())')) {
    reportError(file, 'checker/run.py must exit with the decorated check() result')
  }
  for (const helper of [
    'class TargetContext',
    'class AdContext',
    'class KothContext',
    'class Mumble',
    'class Offline',
    'def ad_checker',
    'def koth_checker',
  ]) {
    if (!librarySource.includes(helper)) {
      reportError(file, `checker/lib.py does not provide ${helper}`)
    }
  }
  for (const transportHelper of [
    'http.client',
    'socket',
    'def http_get',
    'def get_text',
    'def expect_text',
  ]) {
    if (librarySource.includes(transportHelper)) {
      reportError(
        file,
        `checker/lib.py must stay protocol-neutral; found ${transportHelper}`,
      )
    }
  }
  const contractSource = `${source}\n${librarySource}`
  for (const variable of [
    'RSCTF_ACTION',
    'RSCTF_TARGET_IP',
    'RSCTF_TARGET_PORT',
    'RSCTF_ROUND',
    'RSCTF_TEAM_ID',
    'RSCTF_CHALLENGE_ID',
  ]) {
    if (!contractSource.includes(variable)) {
      reportError(file, `checker source does not reference ${variable}`)
    }
  }
  if (model.type === 'AttackDefense') {
    if (!contractSource.includes('RSCTF_FLAG')) {
      reportError(file, 'AttackDefense checker source does not reference RSCTF_FLAG')
    }
    if (!/@ad_checker\s*\ndef check\s*\(/.test(source) || source.includes('@koth_checker')) {
      reportError(file, 'AttackDefense run.py must decorate check with @ad_checker')
    }
  }
  if (model.type === 'KingOfTheHill') {
    if (!/@koth_checker\s*\ndef check\s*\(/.test(source) || source.includes('@ad_checker')) {
      reportError(file, 'KingOfTheHill run.py must decorate check with @koth_checker')
    }
    if (source.includes('RSCTF_FLAG')) {
      reportError(file, 'KingOfTheHill run.py must not use RSCTF_FLAG')
    }
  }
  if (checkerImage) {
    reportError(file, 'local checker source and checkerImage must not both be configured')
  }
}

function validateEvent(file, model) {
  if (!model || !checkKnownKeys(model, EVENT_KEYS, file, '.gzevent')) return
  if (typeof model.title !== 'string' || model.title.trim() === '') {
    reportError(file, 'title is required')
  }
  if (model.hidden !== true) {
    reportError(file, 'documentation event must start with hidden: true')
  }
  if (model.ad !== undefined && checkKnownKeys(model.ad, EVENT_AD_KEYS, file, '.gzevent ad')) {
    for (const key of [
      'tickSeconds',
      'flagLifetimeTicks',
      'warmupSeconds',
      'resetCooldownMinutes',
      'snapshotRetentionDays',
      'minGracePeriodSeconds',
    ]) {
      if (model.ad[key] !== undefined && !positiveInteger(model.ad[key])) {
        reportError(file, `ad.${key} must be a positive integer`)
      }
    }
    if (
      model.ad.getflagWindowFraction !== undefined
      && (typeof model.ad.getflagWindowFraction !== 'number'
        || model.ad.getflagWindowFraction <= 0
        || model.ad.getflagWindowFraction > 1)
    ) {
      reportError(file, 'ad.getflagWindowFraction must be in (0, 1]')
    }
  }
}

function validateChallenge(file, model) {
  if (!model || !checkKnownKeys(model, CHALLENGE_KEYS, file, 'challenge')) return null
  if (typeof model.name !== 'string' || model.name.trim() === '') {
    reportError(file, 'name is required')
  }
  if (!TYPES.includes(model.type)) reportError(file, `unknown challenge type: ${model.type}`)
  if (model.ignore === true) reportError(file, 'ignore: true would skip this example')
  if (model.category !== undefined && !CATEGORIES.has(model.category)) {
    reportError(file, `unknown category: ${model.category}`)
  }
  if (typeof model.type === 'string' && typeof model.category === 'string') {
    checkChallengeLayout(file, model)
  }
  if (
    model.minScoreRate !== undefined
    && (typeof model.minScoreRate !== 'number' || model.minScoreRate < 0 || model.minScoreRate > 1)
  ) {
    reportError(file, 'minScoreRate must be in [0, 1]')
  }
  if (model.difficulty !== undefined && (typeof model.difficulty !== 'number' || model.difficulty <= 0)) {
    reportError(file, 'difficulty must be positive')
  }

  if (model.provide !== undefined) checkSafeProvide(file, model.provide)
  if (model.type?.endsWith('Attachment') && model.provide === undefined) {
    reportError(file, 'attachment examples must name an explicit provide path')
  }

  if (CONTAINER_TYPES.has(model.type)) {
    if (!checkKnownKeys(model.container, CONTAINER_KEYS, file, 'container')) return model.type
    const container = model.container
    if (Object.hasOwn(container, 'containerImage')) {
      reportError(file, 'containerImage must be omitted so Repository Bindings auto-builds ./src/Dockerfile')
    }
    for (const key of ['memoryLimit', 'cpuCount', 'storageLimit']) {
      if (container[key] !== undefined && !positiveInteger(container[key])) {
        reportError(file, `container.${key} must be positive`)
      }
    }
    if (container.storageLimit !== undefined) {
      reportError(file, 'omit container.storageLimit from runnable examples; it is not enforced')
    }
    if (!positiveInteger(container.exposePort) || container.exposePort > 65535) {
      reportError(file, 'container.exposePort must be in 1..65535')
    }
    const dockerfile = resolve(dirname(file), 'src', 'Dockerfile')
    const app = resolve(dirname(file), 'src', 'app.py')
    if (!existsSync(dockerfile) || !existsSync(app)) {
      reportError(file, 'auto-built sample image must provide src/Dockerfile and src/app.py')
    }
    if (
      container.enableTrafficCapture !== undefined
      && (model.type !== 'AttackDefense' || model.ad?.selfHosted === true)
    ) {
      reportError(file, 'container.enableTrafficCapture applies only to platform-hosted A&D')
    }
    if (container.enableSharedContainer !== undefined && model.type !== 'StaticContainer') {
      reportError(file, 'container.enableSharedContainer applies only to StaticContainer')
    }
    if (
      model.type === 'KingOfTheHill'
      && existsSync(dockerfile)
      && !readFileSync(dockerfile, 'utf8').includes('chmod 01777 /koth')
    ) {
      reportError(file, 'KotH Dockerfile must make /koth writable for arbitrary non-root UIDs')
    }
  } else if (model.container !== undefined) {
    reportError(file, `${model.type} must not define a container block`)
  }

  if (model.ad !== undefined && checkKnownKeys(model.ad, AD_KEYS, file, 'ad')) {
    if (model.ad.sshRequiresFlag !== undefined) {
      reportError(file, 'omit ad.sshRequiresFlag from runnable examples; it is not enforced')
    }
    if (model.type === 'KingOfTheHill') {
      for (const key of ['allowSelfReset', 'selfHosted']) {
        if (model.ad[key] !== undefined) {
          reportError(file, `ad.${key} does not apply to KingOfTheHill`)
        }
      }
    }
    if (model.type === 'AttackDefense' && model.ad.selfHosted === true) {
      for (const key of ['allowEgress', 'allowSelfReset']) {
        if (model.ad[key] !== undefined) {
          reportError(file, `ad.${key} does not constrain a self-hosted service`)
        }
      }
    }
  }
  if (model.type === 'AttackDefense' || model.type === 'KingOfTheHill') {
    if (!isRecord(model.ad)) reportError(file, `${model.type} must define an ad block`)
    checkChecker(file, model)
  } else if (model.ad !== undefined) {
    reportError(file, `${model.type} must not define an ad block`)
  }

  if (model.type === 'StaticAttachment' || model.type === 'StaticContainer') {
    if (!Array.isArray(model.flags) || model.flags.length === 0) {
      reportError(file, `${model.type} must include at least one static flag`)
    }
  }
  if (model.type === 'AttackDefense') {
    if (typeof model.flagTemplate !== 'string' || !/\[(?:TEAM_HASH|GUID)\]/.test(model.flagTemplate)) {
      reportError(file, 'AttackDefense must use TEAM_HASH or GUID in flagTemplate')
    }
  }
  if (model.type === 'AttackDefense' || model.type === 'KingOfTheHill') {
    if (model.flags !== undefined) reportError(file, `${model.type} must not define static flags`)
  }
  if (model.type === 'KingOfTheHill' && model.flagTemplate !== undefined) {
    reportError(file, 'KingOfTheHill must not define flagTemplate')
  }
  if (model.type === 'DynamicContainer') {
    const template = model.container?.flagTemplate ?? model.flagTemplate
    if (typeof template !== 'string' || !/\[(?:TEAM_HASH|GUID)\]/.test(template)) {
      reportError(file, 'DynamicContainer must use TEAM_HASH or GUID in flagTemplate')
    }
  }
  if (model.type === 'DynamicAttachment') {
    notices.push(
      `${relative(ROOT, file)}: expected limitation — current rsctf imports this schema but does not assign per-team flag attachments`,
    )
  }
  return model.type
}

function main() {
  const allFiles = walk(ROOT)
  const events = allFiles.filter((file) => file.endsWith(`${sep}.gzevent`))
  if (events.length !== 1) {
    errors.push(`expected exactly one .gzevent below ${ROOT}, found ${events.length}`)
  }

  let challengeFiles = []
  if (events.length === 1) {
    const event = parseFile(events[0])
    validateEvent(events[0], event)
    challengeFiles = walk(dirname(events[0])).filter((file) =>
      file.endsWith(`${sep}challenge.yaml`) || file.endsWith(`${sep}challenge.yml`),
    )
  }
  if (challengeFiles.length !== EXPECTED_CHALLENGE_COUNT) {
    errors.push(
      `expected exactly ${EXPECTED_CHALLENGE_COUNT} challenge manifests, found ${challengeFiles.length}`,
    )
  }

  const foundTypes = []
  const attackDefenseHostingModes = []
  const names = new Map()
  for (const file of challengeFiles) {
    const model = parseFile(file)
    const type = validateChallenge(file, model)
    if (type) foundTypes.push(type)
    if (type === 'AttackDefense') attackDefenseHostingModes.push(model.ad?.selfHosted)
    if (typeof model?.name === 'string') {
      if (names.has(model.name)) {
        reportError(file, `duplicate challenge name also used by ${relative(ROOT, names.get(model.name))}`)
      }
      names.set(model.name, file)
    }
  }

  for (const [type, expectedCount] of EXPECTED_TYPE_COUNTS) {
    const count = foundTypes.filter((candidate) => candidate === type).length
    if (count !== expectedCount) {
      errors.push(`expected exactly ${expectedCount} ${type} manifest(s), found ${count}`)
    }
  }
  for (const selfHosted of [false, true]) {
    const count = attackDefenseHostingModes.filter((candidate) => candidate === selfHosted).length
    if (count !== 1) {
      errors.push(
        `expected exactly one AttackDefense manifest with ad.selfHosted: ${selfHosted}, found ${count}`,
      )
    }
  }
  if (new Set(checkerLibraries.map(({ source }) => source)).size !== 1) {
    errors.push('every checker/lib.py must remain byte-identical')
  }

  for (const notice of notices) console.log(`NOTICE: ${notice}`)
  if (errors.length > 0) {
    for (const error of errors) console.error(`ERROR: ${error}`)
    console.error(`\nValidation failed with ${errors.length} error(s).`)
    process.exitCode = 1
    return
  }
  console.log(
    `OK: validated one event, all ${TYPES.length} challenge types, and both AttackDefense hosting modes.`,
  )
  console.log('OK: manifests use known keys, local builds, and protocol-neutral checker libraries.')
}

main()
