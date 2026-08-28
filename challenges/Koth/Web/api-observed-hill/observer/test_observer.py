from __future__ import annotations

from datetime import datetime, timedelta, timezone
import email.utils
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import observer


class RetryPolicyTests(unittest.TestCase):
    def test_http_retry_after_supports_seconds_and_dates(self) -> None:
        now = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(observer._retry_after_seconds({"Retry-After": "7"}, now), 7.0)
        future = email.utils.format_datetime(now + timedelta(seconds=11), usegmt=True)
        self.assertEqual(observer._retry_after_seconds({"Retry-After": future}, now), 11.0)
        self.assertIsNone(observer._retry_after_seconds({"Retry-After": "invalid"}, now))

    def test_classification_stops_auth_schema_and_non_stale_conflicts(self) -> None:
        self.assertIs(
            observer._failure_disposition(observer.RefereeHttpError(401, "bad signature")),
            observer.FailureDisposition.PERMANENT,
        )
        self.assertIs(
            observer._failure_disposition(RuntimeError("unexpected objective schema")),
            observer.FailureDisposition.PERMANENT,
        )
        self.assertIs(
            observer._failure_disposition(observer.RefereeHttpError(409, "objectives are frozen")),
            observer.FailureDisposition.PERMANENT,
        )

    def test_classification_retries_capacity_and_stale_context(self) -> None:
        self.assertIs(
            observer._failure_disposition(observer.RefereeHttpError(503, "busy")),
            observer.FailureDisposition.RETRYABLE,
        )
        self.assertIs(
            observer._failure_disposition(observer.RefereeHttpError(409, "context changed; fetch context and retry")),
            observer.FailureDisposition.RETRYABLE,
        )

    def test_retry_delay_uses_full_jitter_honors_retry_after_and_is_capped(self) -> None:
        self.assertEqual(observer._retry_delay(3, 5, random_value=lambda: 0.25), 5.0)
        self.assertEqual(observer._retry_delay(3, 5, 17, random_value=lambda: 0.25), 17.0)
        self.assertEqual(
            observer._retry_delay(20, 300, 600, random_value=lambda: 1.0),
            observer.MAX_RETRY_DELAY_SECONDS,
        )


class PersistenceTests(unittest.TestCase):
    def test_config_uses_a_managed_state_path_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as state_root:
            environment = {
                "RSCTF_KOTH_OBSERVER_SECRET": "koth_api_" + "a" * 32,
                "RSCTF_ORIGIN": "https://ctf.example",
                "RSCTF_GAME_ID": "7",
                "RSCTF_CHALLENGE_ID": "9",
                "RSCTF_KOTH_HILL_URL": "https://hill.example",
                "XDG_STATE_HOME": state_root,
            }
            with patch.dict(os.environ, environment, clear=True):
                config = observer.load_config(False)
            self.assertEqual(
                config.state_file,
                Path(state_root) / "rsctf-koth-observer" / "game-7-challenge-9.json",
            )

    def test_submitted_digest_survives_client_restart(self) -> None:
        with tempfile.TemporaryDirectory() as state_root:
            config = observer.Config(
                origin="https://ctf.example",
                game_id=7,
                challenge_id=9,
                secret="koth_api_" + "a" * 32,
                hill_url="https://hill.example",
                poll_seconds=5,
                timeout_seconds=5,
                state_file=Path(state_root) / "observer.json",
            )
            first = observer.RefereeClient(config)
            first.last_submitted_digest = "a" * 64
            first._save_state()

            restored = observer.RefereeClient(config)
            self.assertEqual(restored.last_submitted_digest, "a" * 64)


if __name__ == "__main__":
    unittest.main()
