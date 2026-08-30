"""Focused tests for the managed Leaderboard reporter contract."""

import json
import os
import unittest
from unittest.mock import patch

from reporter import Config, ManagedReporter, RoundContext, TeamTotals, load_config


class ConfigTests(unittest.TestCase):
    def test_absent_managed_environment_disables_reporting(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(load_config())

    def test_partial_managed_environment_fails_closed(self):
        with patch.dict(os.environ, {"RSCTF_KOTH_GAME_ID": "7"}, clear=True):
            with self.assertRaisesRegex(ValueError, "incomplete managed reporter"):
                load_config()


class SnapshotTests(unittest.TestCase):
    def reporter(self):
        config = Config(
            game_id=7,
            challenge_id=42,
            secret="koth_target_abcdefghijklmnopqrstuvwxyz",
            context_url="http://rsctf.test/context",
            observation_url="http://rsctf.test/observations",
            poll_seconds=5,
            timeout_seconds=5,
        )
        return ManagedReporter(config, lambda _after: {})

    def context(self):
        return RoundContext(
            opaque="a" * 64,
            cycle_number=1,
            reset_attempt=0,
            round_number=2,
            starts_at=30_001,
            ends_at=90_000,
            cycle_ends_at=120_000,
            eligible_hashes=frozenset({"b" * 64, "c" * 64}),
            objective_ids=(),
            objective_schema_hash=None,
        )

    def test_unique_best_team_receives_only_crown(self):
        reporter = self.reporter()
        reporter.waves[30_000] = {
            "b" * 64: TeamTotals(1, 1, 5, 5, 40, 60, 1),
            "c" * 64: TeamTotals(1, 1, 4, 5, 30, 60, 2),
        }

        body = json.loads(reporter._body(self.context(), 92_000))

        self.assertEqual(body["objectiveIds"], ["proof-strength", "solve-speed"])
        self.assertEqual(len(body["waves"]), 1)
        crowns = [team["tokenHash"] for team in body["waves"][0]["teams"] if team["isCrown"]]
        self.assertEqual(crowns, ["b" * 64])

    def test_exact_tie_has_no_crown(self):
        reporter = self.reporter()
        reporter.waves[30_000] = {
            "b" * 64: TeamTotals(1, 1, 5, 5, 30, 60, 1),
            "c" * 64: TeamTotals(1, 1, 5, 5, 30, 60, 2),
        }

        body = json.loads(reporter._body(self.context(), 92_000))

        self.assertFalse(any(team["isCrown"] for team in body["waves"][0]["teams"]))


if __name__ == "__main__":
    unittest.main()
