import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "dot_codex/hooks/executable_daily-usage.py"
loader = importlib.machinery.SourceFileLoader("daily_guard", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
guard = importlib.util.module_from_spec(spec)
loader.exec_module(guard)


def timestamp(day=12, hour=12, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=guard.KOREA).timestamp()


def snapshot(points, now=None, account="a", reset=None, plan="pro"):
    now = timestamp() if now is None else now
    return {"account_key": account * 64, "plan": plan, "used_percent": points,
            "resets_at": int(timestamp(19)) if reset is None else reset, "observed_at": now}


class DailyGuardTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = Path(self.scratch.name)
        self.addCleanup(self.scratch.cleanup)

    def record(self, points, now=None, **kwargs):
        sample = snapshot(points, now, **kwargs)
        return guard.record(sample, self.root / "state", sample["observed_at"])

    def test_warning_and_cap_use_total_weekly_percentage_points(self):
        self.record(7)
        self.assertTrue(self.record(24)["allowed"])
        self.assertTrue(self.record(25)["warning"])
        self.assertTrue(self.record(32)["allowed"])
        self.assertFalse(self.record(33)["allowed"])
        self.assertFalse(self.record(42)["allowed"])

    def test_midnight_resets_cap_and_counts_boundary_gap(self):
        self.record(40, timestamp(12, 23, 59))
        after = self.record(42, timestamp(13, 0, 1))
        self.assertTrue(after["allowed"])
        self.assertEqual(after["daily_points"], 2)
        self.assertEqual(after["day"], "2026-10-13")
        self.assertEqual(after["unblock_at"], "2026-10-14T00:00:00+09:00")

    def test_hook_restart_and_missed_days_do_not_forgive_usage(self):
        self.record(9, timestamp(12))
        later = self.record(43, timestamp(14))
        self.assertEqual(later["daily_points"], 34)
        self.assertFalse(later["allowed"])

    def test_first_reading_is_conservative(self):
        first = self.record(35)
        self.assertFalse(first["allowed"])
        self.assertEqual(first["daily_points"], 35)
        self.assertIn("first reading", first["coverage"])

    def test_weekly_reset_does_not_clear_today_or_reopen_cap(self):
        self.record(34)
        reset = self.record(2, timestamp(12, 13), reset=int(timestamp(26)))
        self.assertEqual(reset["daily_points"], 36)
        self.assertFalse(reset["allowed"])
        self.assertIn("Quota reset", reset["uncertain"])
        still = self.record(3, timestamp(12, 14), reset=int(timestamp(26)))
        self.assertFalse(still["allowed"])
        next_day = self.record(4, timestamp(13), reset=int(timestamp(26)))
        self.assertTrue(next_day["allowed"])
        self.assertEqual(next_day["daily_points"], 1)

    def test_earned_reset_is_unknown_even_before_scheduled_reset(self):
        self.record(15)
        reset = self.record(0, timestamp(12, 13), reset=int(timestamp(20)))
        self.assertFalse(reset["allowed"])
        self.assertEqual(reset["daily_points"], 15)

    def test_quota_decrease_without_reset_is_sticky_unknown(self):
        self.record(20)
        self.assertFalse(self.record(19, timestamp(12, 13))["allowed"])
        self.assertFalse(self.record(22, timestamp(12, 14))["allowed"])

    def test_accounts_are_separate_and_plan_changes_are_unknown(self):
        self.record(35, account="a")
        self.assertTrue(self.record(5, account="b")["allowed"])
        changed = self.record(7, timestamp(12, 13), account="b", plan="promax")
        self.assertFalse(changed["allowed"])
        self.assertIn("Plan changed", changed["uncertain"])

    def test_missing_stale_or_invalid_metadata_denies(self):
        for mutation in ({"resets_at": None}, {"used_percent": True}, {"used_percent": -1},
                         {"used_percent": 101}, {"observed_at": timestamp() - 31}):
            sample = snapshot(5)
            sample.update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(guard.GuardError):
                guard.record(sample, self.root / "state", timestamp())

    def test_older_concurrent_sample_does_not_roll_back_state(self):
        self.record(32, timestamp(12, 12, 1))
        earlier = snapshot(31, timestamp(12, 12, 1) - 10)
        result = guard.record(earlier, self.root / "state", timestamp(12, 12, 1))
        self.assertEqual(result["daily_points"], 32)

    def test_clock_rollback_and_corrupt_state_deny(self):
        self.record(5, timestamp(12, 13))
        with self.assertRaises(guard.GuardError):
            self.record(5, timestamp(12, 12))
        path = self.root / "state" / ("a" * 64 + ".json")
        path.write_text("{broken")
        with self.assertRaises(guard.GuardError):
            self.record(5)

    def test_manual_baseline_is_explicit_and_records_previous_consumption(self):
        self.record(40)
        sample = snapshot(40)
        result = guard.record(sample, self.root / "state", timestamp(), baseline=3)
        self.assertTrue(result["allowed"])
        state = json.loads((self.root / "state" / ("a" * 64 + ".json")).read_text())
        self.assertEqual(state["manual_baseline"]["previous_points"], 40)
        self.assertEqual(state["manual_baseline"]["declared_points"], 3)

    def test_atomic_private_state(self):
        self.record(5)
        path = self.root / "state" / ("a" * 64 + ".json")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(list(path.parent.glob(".state-*")), [])

    def test_parallel_public_hooks_share_one_state_without_double_counting(self):
        self.record(7)
        fixture = self.root / "snapshot.json"
        fixture.write_text(json.dumps(snapshot(32)))
        commands = [sys.executable, "-B", str(SOURCE), "hook", "--snapshot", str(fixture),
                    "--state-dir", str(self.root / "state"), "--now", str(timestamp())]
        processes = [subprocess.Popen(commands, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True) for _ in range(8)]
        for process in processes:
            stdout, stderr = process.communicate(json.dumps({"hook_event_name": "UserPromptSubmit"}), timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn("systemMessage", json.loads(stdout))
        self.assertEqual(self.record(32)["daily_points"], 32)

    def test_public_prompt_blocks_but_stop_ends_without_continuation(self):
        fixture = self.root / "snapshot.json"
        fixture.write_text(json.dumps(snapshot(33)))
        for event in ("UserPromptSubmit", "Stop"):
            result = subprocess.run([sys.executable, "-B", str(SOURCE), "hook", "--snapshot", str(fixture),
                                     "--state-dir", str(self.root / "state"), "--now", str(timestamp())],
                                    input=json.dumps({"hook_event_name": event}), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            if event == "Stop":
                self.assertFalse(output["continue"])
                self.assertNotIn("decision", output)
            else:
                self.assertEqual(output["decision"], "block")

    def test_public_hook_denies_missing_fixture_without_traceback(self):
        result = subprocess.run([sys.executable, "-B", str(SOURCE), "hook", "--snapshot", str(self.root / "missing")],
                                input=json.dumps({"hook_event_name": "UserPromptSubmit"}), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["decision"], "block")
        self.assertNotIn("Traceback", result.stderr)

    def test_thresholds_are_configurable_in_the_hook_command(self):
        fixture = self.root / "snapshot.json"
        fixture.write_text(json.dumps(snapshot(7)))
        result = subprocess.run([sys.executable, "-B", str(SOURCE), "hook", "--snapshot", str(fixture),
                                 "--state-dir", str(self.root / "state"), "--now", str(timestamp()),
                                 "--daily-cap", "10", "--warn-at", "5"],
                                input=json.dumps({"hook_event_name": "UserPromptSubmit"}), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("7/10", json.loads(result.stdout)["systemMessage"])

    def test_invalid_stop_hook_arguments_stop_instead_of_continuing(self):
        for arguments in (("--daily-cap", "2"), ("--daily-cap", "invalid")):
            result = subprocess.run([sys.executable, "-B", str(SOURCE), "hook", *arguments],
                                    input=json.dumps({"hook_event_name": "Stop"}), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)["continue"])
            self.assertNotIn("decision", json.loads(result.stdout))

    def test_metadata_finds_weekly_window_in_either_slot(self):
        account = {"account": {"type": "chatgpt", "email": "fixture@example.invalid", "planType": "pro"}}
        weekly = {"usedPercent": 7, "windowDurationMins": 10080, "resetsAt": int(timestamp(19))}
        for slot in ("primary", "secondary"):
            value = guard.snapshot_from_metadata(account, {"rateLimitsByLimitId": {"codex": {slot: weekly}}}, timestamp())
            self.assertEqual(value["used_percent"], 7)
            self.assertNotIn("email", value)
        with self.assertRaises(guard.GuardError):
            guard.snapshot_from_metadata(account, {"rateLimits": {"primary": weekly, "secondary": weekly}}, timestamp())



if __name__ == "__main__":
    unittest.main()
