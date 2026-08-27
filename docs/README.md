# Documentation

Use this page as the human entry point. Pick the job you are doing instead of
reading every reference front to back.

| I want to… | Read |
| --- | --- |
| create my first challenge | [Getting started](getting-started.md) |
| look up `.gzevent` or `challenge.yaml` fields | [Manifest reference](configuration.md) |
| write or debug an A&D/KotH checker | [Checker development](checkers.md) |
| run a fair blind solve | [Playtesting](playtesting.md) |
| import or rescan the repository | [Repository Bindings](importing.md) |
| prepare deterministic variants or solve receipts | [Provenance](provenance.md) |
| deploy the signed Leaderboard KotH observer | [Trusted KotH referee](koth-referee.md) |
| decide whether a challenge is ready to import | [Release checklist](release-checklist.md) |

The root [README](../README.md) is intentionally short. Challenge packages contain
only manifests, player artifacts, source, generators, observers, and checkers. Put
maintainer documentation here so teammates have one place to search.

AI coding agents use the same facts through the repository's [AGENTS.md](../AGENTS.md)
and `.agents/skills/rsctf-challenge-authoring/` workflow.
