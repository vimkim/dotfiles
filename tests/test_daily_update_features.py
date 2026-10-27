"""Feature boundaries that require no network or live tool upgrades."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "private_dot_config/my-scripts")
)
from daily_update import cli, projects, skills, state, tools
from daily_update.common import Failed, Results


class FeatureTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        env = patch.dict(
            os.environ,
            {
                "HOME": str(self.home),
                "XDG_CACHE_HOME": str(self.home / "cache"),
                "XDG_CONFIG_HOME": str(self.home / "config"),
                "CLAUDE_CONFIG_DIR": str(self.home / "claude"),
            },
        )
        env.start()
        self.addCleanup(env.stop)
        self.output = io.StringIO()
        for redirect in (redirect_stdout, redirect_stderr):
            context = redirect(self.output)
            context.__enter__()
            self.addCleanup(context.__exit__, None, None, None)

    def lock(self, entries):
        path = skills.lock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": 3, "skills": entries}))
        return path

    def response(self, *args, code=0, stdout="", **kwargs):
        return subprocess.CompletedProcess(args, code, stdout, "")

    def test_local_tools_override_path_and_brew_targets_only_owned_codex(self):
        local = self.home / ".local/bin/codex"
        local.parent.mkdir(parents=True)
        local.write_text("native")
        local.chmod(0o755)
        with (
            patch.object(tools.shutil, "which", return_value="/fake/brew"),
            patch.object(tools, "command") as run,
        ):
            self.assertEqual(tools.resolve("codex"), str(local))
            run.side_effect = [self.response(stdout="/brew\n"), self.response()]
            tools.codex()
            self.assertEqual(run.call_args.args, (str(local), "update"))
            target = self.home / "brew/Caskroom/codex/version/codex"
            target.parent.mkdir(parents=True)
            target.touch()
            local.unlink()
            local.symlink_to(target)
            target.chmod(0o755)
            run.reset_mock()
            run.side_effect = [
                self.response(stdout=str(self.home / "brew") + "\n"),
                self.response(stdout="codex 1.0\n"),
                self.response(),
            ]
            tools.codex()
            self.assertEqual(
                run.call_args.args, ("/fake/brew", "upgrade", "--cask", "codex")
            )

    def test_configured_collection_protects_custom_identity_path_and_collision(self):
        root = self.home / "custom collection"
        (root / "skills/collision").mkdir(parents=True)
        (root / "skills/collision/SKILL.md").touch()
        collection = projects.Project(
            "custom", root, "vimkim/custom-skills", "collection"
        )
        self.lock(
            {
                "personal": {"source": "git@github.com:vimkim/custom-skills.git"},
                "local": {"source": str(root)},
                "collision": {"source": "someone/other"},
                "eligible": {"source": "someone/other"},
            }
        )
        self.assertEqual(skills.inventory([collection])[1], ["eligible"])
        (root / "skills/collision/SKILL.md").unlink()
        (root / "skills/collision").rmdir()
        self.assertEqual(skills.inventory([collection])[1], ["collision", "eligible"])

    def test_prune_retains_original_lock_and_recovers_installed_files(self):
        entries = {
            "obsolete": {"source": "someone/other", "sourceType": "github"},
            "personal": {"source": "vimkim/custom-skills"},
        }
        path = self.lock(entries)
        before = path.read_bytes()
        installed = skills.store_path() / "obsolete"
        installed.mkdir(parents=True)
        (installed / "SKILL.md").write_text("recover me")
        claude = skills.claude_skills()
        claude.mkdir(parents=True)
        (claude / "obsolete").symlink_to(installed)
        collection = projects.Project(
            "custom", self.home / "missing", "vimkim/custom-skills", "collection"
        )
        with (
            patch.object(skills.shutil, "which", return_value="/fake/gh"),
            patch.object(
                skills, "command", return_value=self.response(stdout="remaining\n")
            ),
        ):
            skills.prune([collection], state.State())
        trash = next((state.State().directory / "trash").iterdir())
        self.assertEqual((trash / ".skill-lock.json.bak").read_bytes(), before)
        self.assertEqual((trash / "obsolete/SKILL.md").read_text(), "recover me")
        self.assertFalse(installed.exists())
        self.assertFalse((claude / "obsolete").is_symlink())
        self.assertEqual(
            json.loads(path.read_text())["skills"], {"personal": entries["personal"]}
        )

    def test_failed_or_unexpected_upstream_evidence_never_marks_installed_skill_stale(
        self,
    ):
        self.lock({"installed": {"source": "someone/other", "sourceType": "github"}})
        (skills.store_path() / "installed").mkdir(parents=True)
        for code, output in ((1, "unrelated\n"), (0, ""), (0, '{"error": "404"}\n')):
            with (
                self.subTest(code=code, output=output),
                patch.object(skills.shutil, "which", return_value="/fake/gh"),
                patch.object(
                    skills,
                    "command",
                    return_value=self.response(code=code, stdout=output),
                ),
            ):
                self.assertEqual(skills.stale([]), {})

    def test_empty_eligible_list_never_updates_and_malformed_lock_fails_closed(self):
        collection = projects.Project(
            "custom", self.home / "missing", "vimkim/custom-skills", "collection"
        )
        path = self.lock({"personal": {"source": "vimkim/custom-skills"}})
        with patch.object(skills, "upgrade") as upgrade:
            skills.update([collection])
            upgrade.assert_not_called()
            path.write_text("{broken")
            with self.assertRaises(Failed):
                skills.update([collection])
            upgrade.assert_not_called()

    def test_github_managed_gh_stack_is_excluded_from_legacy_update_and_prune(self):
        path = self.lock({"gh-stack": {"source": "github/gh-stack", "sourceType": "github"}})
        original = path.read_bytes()
        with (
            patch.object(skills, "upgrade") as upgrade,
            patch.object(skills, "command") as command,
        ):
            skills.update([])
            skills.prune([], state.State())
            upgrade.assert_not_called()
            command.assert_not_called()
        self.assertEqual(path.read_bytes(), original)

    def test_reminders_are_offline_and_reuse_legacy_stamp_and_stale_cache(self):
        cached = state.State()
        cached.cache_stale({f"old{i}": "missing" for i in range(10)})
        with (
            patch.object(
                tools, "command", side_effect=AssertionError("tool command at startup")
            ),
            patch.object(
                projects,
                "load_projects",
                side_effect=AssertionError("config read at startup"),
            ),
        ):
            self.assertEqual(cli.main(["--remind"]), 0)
            self.assertIn("and 2 more", self.output.getvalue())
            cached.mark()
            self.output.truncate(0)
            self.output.seek(0)
            self.assertEqual(cli.main(["--remind"]), 0)
            self.assertEqual(self.output.getvalue(), "")
            self.assertEqual(cli.main(["--status"]), 0)
            self.assertIn("done", self.output.getvalue())
            self.assertEqual(cli.main(["--reset"]), 0)
            self.assertTrue(cached.pending())

    def test_missing_tool_skips_and_failed_step_does_not_stop_next_step(self):
        results = Results()
        with patch.object(tools, "resolve", return_value=None):
            results.run("missing", lambda: tools.upgrade("absent", "update"))
        with (
            patch.object(tools, "resolve", return_value="/fake/tool"),
            patch.object(tools, "command", return_value=self.response(code=7)),
        ):
            results.run("bad", lambda: tools.upgrade("tool", "update"))
        finished = []
        results.run("good", lambda: finished.append(True))
        self.assertEqual(finished, [True])
        self.assertEqual(results.failed, ["bad"])
        self.assertEqual(results.skipped, ["missing"])
        self.assertEqual(results.summary(), 1)


if __name__ == "__main__":
    unittest.main()
