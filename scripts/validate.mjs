#!/usr/bin/env node

/**
 * Package-free validator for the rsctf repository-binding example.
 *
 * This intentionally implements only the small, readable YAML subset used by
 * this example. Keeping it local avoids an npm install in CI while still making
 * indentation, duplicate keys, known fields, paths, local build contexts, and
 * checker layout fail closed. rsctf remains the authoritative importer schema.
 */

import { existsSync, lstatSync, readFileSync, readdirSync } from 'node:fs'
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

const AD_KEYS = new Set(['checkerImage', 'allowEgress', 'allowSelfReset', 'sshRequiresFlag', 'selfHosted'])

const TYPES = [
  'StaticAttachment',
  'DynamicAttachment',
  'StaticContainer',
  'DynamicContainer',
  'AttackDefense',
  'KingOfTheHill',
]

const EXPECTED_TYPE_COUNTS = new Map(TYPES.map((type) => [type, type === 'AttackDefense' ? 2 : 1]))

const EXPECTED_CHALLENGE_COUNT = [...EXPECTED_TYPE_COUNTS.values()].reduce((total, count) => total + count, 0)

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

const CONTAINER_TYPES = new Set(['StaticContainer', 'DynamicContainer', 'AttackDefense', 'KingOfTheHill'])

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

function registeredChecks(source) {
  const lines = source.replaceAll('\r\n', '\n').split('\n')
  const checks = []
  for (let index = 0; index < lines.length; index += 1) {
    if (lines[index] !== '@checker') continue
    const definition = /^def ([A-Za-z_][A-Za-z0-9_]*)\(context: (AdContext|KothContext)\) -> None:$/.exec(
      lines[index + 1] ?? ''
    )
    if (!definition) continue

    const body = []
    for (let cursor = index + 2; cursor < lines.length; cursor += 1) {
      const line = lines[cursor]
      if (line.trim() !== '' && !line.startsWith(' ')) break
      body.push(line)
    }
    checks.push({
      name: definition[1],
      context: definition[2],
      body: body.join('\n'),
    })
  }
  return checks
}

function checkChallengeLayout(file, model) {
  const parts = relative(ROOT, file).split(sep)
  const expectedMode = model.type === 'AttackDefense' ? 'AD' : model.type === 'KingOfTheHill' ? 'Koth' : 'Jeopardy'
  if (
    parts.length !== 4 ||
    parts[0] !== expectedMode ||
    parts[1] !== model.category ||
    parts[2].trim() === '' ||
    !['challenge.yaml', 'challenge.yml'].includes(parts[3])
  ) {
    reportError(
      file,
      `must use ${expectedMode}/<category>/<challenge>/challenge.yaml and match category ${model.category}`
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
  const packagePath = relative(ROOT, packageRoot).split(sep).join('/')
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

  const requirements = resolve(checkerRoot, 'requirements.txt')
  if (existsSync(requirements)) {
    const requirementsSource = readFileSync(requirements, 'utf8')
    if (Buffer.byteLength(requirementsSource, 'utf8') > 16 * 1024) {
      reportError(file, 'checker requirements.txt exceeds the 16 KiB platform limit')
    }
    const requirementLines = requirementsSource
      .split(/\r?\n/)
      .map((line) => line.split('#', 1)[0].trim())
      .filter((line) => line !== '')
    if (requirementLines.length > 32) {
      reportError(file, 'checker requirements.txt exceeds the 32-package platform limit')
    }
    const packageNames = new Set()
    for (const line of requirementLines) {
      const parts = line.split('==')
      const [name, version] = parts
      const validName =
        parts.length === 2 &&
        name.length > 0 &&
        name.length <= 128 &&
        /^[A-Za-z0-9][A-Za-z0-9_.-]*[A-Za-z0-9]$|^[A-Za-z0-9]$/.test(name)
      const validVersion =
        parts.length === 2 &&
        version.length > 0 &&
        version.length <= 128 &&
        /^[A-Za-z0-9][A-Za-z0-9_.+!-]*[A-Za-z0-9]$|^[A-Za-z0-9]$/.test(version)
      if (!validName || !validVersion) {
        reportError(file, 'checker requirements must use exact package==version pins')
        continue
      }
      const normalizedName = name.toLowerCase().replaceAll(/[-_.]+/g, '-')
      if (packageNames.has(normalizedName)) {
        reportError(file, `checker requirements repeat package ${name}`)
      }
      packageNames.add(normalizedName)
    }
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
  const checks = registeredChecks(source)
  const suiteBody = checks.map(({ body }) => body).join('\n')
  const checkerDecoratorCount = source.match(/^@checker$/gm)?.length ?? 0
  checkerLibraries.push({ file: library, source: librarySource })
  if (!source.includes('from lib import')) {
    reportError(file, 'checker/run.py must import reusable helpers from sibling lib.py')
  }
  for (const helper of [
    'class TargetContext',
    'class AdContext',
    'class KothContext',
    'class Mumble',
    'class Offline',
    'def ad_checker',
    'def checker',
    'def koth_checker',
    'def run_ad_checker',
    'def run_koth_checker',
    'functions = list(_registered_checkers)',
    'secrets.randbelow(index + 1)',
    'for function in functions:',
  ]) {
    if (!librarySource.includes(helper)) {
      reportError(file, `checker/lib.py does not provide ${helper}`)
    }
  }
  if (librarySource.includes('secrets.choice(')) {
    reportError(file, 'checker/lib.py must run the complete suite, not choose one check')
  }
  for (const transportHelper of ['http.client', 'socket', 'def http_get', 'def get_text', 'def expect_text']) {
    if (librarySource.includes(transportHelper)) {
      reportError(file, `checker/lib.py must stay protocol-neutral; found ${transportHelper}`)
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
    if (!source.includes('raise SystemExit(run_ad_checker())')) {
      reportError(file, 'AttackDefense run.py must exit with run_ad_checker()')
    }
    if (checkerDecoratorCount < 2 || checks.length !== checkerDecoratorCount) {
      reportError(file, 'AttackDefense run.py must define at least two typed @checker checks')
    }
    if (source.includes('@ad_checker') || source.includes('@koth_checker')) {
      reportError(file, 'AttackDefense example must use @checker registration')
    }
    for (const check of checks) {
      if (check.context !== 'AdContext') {
        reportError(file, `registered check ${check.name} must accept AdContext`)
      }
    }
    if (!suiteBody.includes('context.flag')) {
      reportError(file, 'registered A&D checker suite must verify context.flag')
    }
  }
  if (model.type === 'KingOfTheHill') {
    if (!source.includes('raise SystemExit(run_koth_checker())')) {
      reportError(file, 'KingOfTheHill run.py must exit with run_koth_checker()')
    }
    if (checkerDecoratorCount < 2 || checks.length !== checkerDecoratorCount) {
      reportError(file, 'KingOfTheHill run.py must define at least two typed @checker checks')
    }
    if (source.includes('@ad_checker') || source.includes('@koth_checker')) {
      reportError(file, 'KingOfTheHill example must use @checker registration')
    }
    for (const check of checks) {
      if (check.context !== 'KothContext') {
        reportError(file, `registered check ${check.name} must accept KothContext`)
      }
    }
    if (!suiteBody.includes('"/health"')) {
      reportError(file, 'registered KotH checker suite must verify /health')
    }
    if (source.includes('RSCTF_FLAG')) {
      reportError(file, 'KingOfTheHill run.py must not use RSCTF_FLAG')
    }
  }
  if (packagePath === 'AD/Pwn/attack-defense-service') {
    if (!existsSync(requirements) || readFileSync(requirements, 'utf8').trim() !== 'pwntools==4.15.0') {
      reportError(file, 'raw TCP checker must pin pwntools==4.15.0 in requirements.txt')
    }
    for (const marker of [
      'os.environ["PWNLIB_NOTERM"] = "1"',
      'from pwn import context as pwn_context, remote',
      'pwn_context.log_level = "critical"',
      'tube.sendline(',
      'tube.recv(',
      'monotonic()',
      'PwnlibException',
      'PING',
      'GET_FLAG',
    ]) {
      if (!source.includes(marker)) {
        reportError(file, `raw TCP checker is missing ${marker}`)
      }
    }
    if (!suiteBody.includes('"PING"') || !suiteBody.includes('"GET_FLAG"')) {
      reportError(file, 'raw TCP checker suite must verify PING and GET_FLAG')
    }
    if (source.includes('HTTPConnection') || source.includes('socket.create_connection')) {
      reportError(file, 'raw TCP checker must use the pinned pwntools tube API')
    }

    const service = resolve(packageRoot, 'src', 'app.py')
    if (existsSync(service)) {
      const serviceSource = readFileSync(service, 'utf8')
      for (const marker of ['socketserver.ThreadingTCPServer', 'PING', 'PONG', 'GET_FLAG']) {
        if (!serviceSource.includes(marker)) {
          reportError(file, `raw TCP service is missing ${marker}`)
        }
      }
      if (serviceSource.includes('http.server')) {
        reportError(file, 'raw TCP service must not use the HTTP server')
      }
    }
  }
  if (packagePath === 'AD/Web/self-hosted-service') {
    if (!existsSync(requirements) || readFileSync(requirements, 'utf8').trim() !== 'httpx==0.28.1') {
      reportError(file, 'self-hosted HTTP checker must pin httpx==0.28.1')
    }
    for (const marker of [
      'import httpx',
      'httpx.Client(',
      'follow_redirects=False',
      'trust_env=False',
      'client.stream(',
      'response.iter_raw(chunk_size=1024)',
      'MAX_RESPONSE_BYTES',
      'httpx.TimeoutException',
      'httpx.NetworkError',
      'httpx.ProtocolError',
      'context.target_ip',
      'context.target_port',
    ]) {
      if (!source.includes(marker)) {
        reportError(file, `self-hosted HTTP checker is missing ${marker}`)
      }
    }
    if (!suiteBody.includes('"/health"') || !suiteBody.includes('"/secret"')) {
      reportError(file, 'self-hosted HTTP checker suite must verify health and flag')
    }
    if (source.includes('HTTPConnection') || source.includes('from pwn import')) {
      reportError(file, 'self-hosted HTTP checker must use the pinned httpx client')
    }
  }
  if (packagePath === 'Koth/Pwn/king-of-the-hill') {
    if (!source.includes('HTTPConnection') || source.includes('from pwn import')) {
      reportError(file, 'KotH checker must remain an HTTP standard-library client')
    }
    if (existsSync(requirements)) {
      reportError(file, 'KotH checker must remain dependency-free')
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
      model.ad.getflagWindowFraction !== undefined &&
      (typeof model.ad.getflagWindowFraction !== 'number' ||
        model.ad.getflagWindowFraction <= 0 ||
        model.ad.getflagWindowFraction > 1)
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
    model.minScoreRate !== undefined &&
    (typeof model.minScoreRate !== 'number' || model.minScoreRate < 0 || model.minScoreRate > 1)
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
      container.enableTrafficCapture !== undefined &&
      (model.type !== 'AttackDefense' || model.ad?.selfHosted === true)
    ) {
      reportError(file, 'container.enableTrafficCapture applies only to platform-hosted A&D')
    }
    if (container.enableSharedContainer !== undefined && model.type !== 'StaticContainer') {
      reportError(file, 'container.enableSharedContainer applies only to StaticContainer')
    }
    if (
      model.type === 'KingOfTheHill' &&
      existsSync(dockerfile) &&
      !readFileSync(dockerfile, 'utf8').includes('chmod 01777 /koth')
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
      `${relative(ROOT, file)}: expected limitation — current rsctf imports this schema but does not assign per-team flag attachments`
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
    challengeFiles = walk(dirname(events[0])).filter(
      (file) => file.endsWith(`${sep}challenge.yaml`) || file.endsWith(`${sep}challenge.yml`)
    )
  }
  if (challengeFiles.length !== EXPECTED_CHALLENGE_COUNT) {
    errors.push(`expected exactly ${EXPECTED_CHALLENGE_COUNT} challenge manifests, found ${challengeFiles.length}`)
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
      errors.push(`expected exactly one AttackDefense manifest with ad.selfHosted: ${selfHosted}, found ${count}`)
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
  console.log(`OK: validated one event, all ${TYPES.length} challenge types, and both AttackDefense hosting modes.`)
  console.log('OK: manifests use local builds, pinned checker wheels, and protocol-neutral libraries.')
}

main()
