"""Verify prv without GitHub: a local bare repository stands in for the remote."""
import hashlib
import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "private_dot_local/bin/executable_prv"


def load_prv():
    loader = SourceFileLoader("prv", str(CLI))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("prv", loader))
    sys.modules["prv"] = module  # dataclasses look the module up here
    loader.exec_module(module)
    return module


prv = load_prv()


def anchor(path):
    return hashlib.sha256(path.encode()).hexdigest()


class ParseTests(unittest.TestCase):
    def test_pr_urls(self):
        hash_ = anchor("src/a.c")
        cases = [
            ("https://github.com/CUBRID/cubrid/pull/8299", None),
            ("https://github.com/CUBRID/cubrid/pull/8299/", None),
            ("https://github.com/CUBRID/cubrid/pull/8299/files?w=1", None),
            ("https://github.com/CUBRID/cubrid/pull/8299/changes#diff-" + hash_, hash_),
            ("https://github.com/CUBRID/cubrid/pull/8299/files#diff-" + hash_ + "R12", hash_),
            ("https://github.com/CUBRID/cubrid/pull/8299/files#diff-" + hash_ + "L3-R5", hash_),
            ("https://github.com/CUBRID/cubrid/pull/8299#issuecomment-123", None),
            ("github.com/CUBRID/cubrid/pull/8299", None),
        ]
        for url, expected_anchor in cases:
            with self.subTest(url=url):
                self.assertEqual(prv.parse_pr_url(url),
                                 prv.PullRequest("CUBRID/cubrid", 8299, expected_anchor))

    def test_rejects_non_pr_urls(self):
        for url in ("https://github.com/CUBRID/cubrid/issues/1",
                    "https://github.com/CUBRID/cubrid/pull/12abc",
                    "https://gitlab.com/CUBRID/cubrid/pull/1",
                    "not a url"):
            with self.subTest(url=url), self.assertRaises(prv.UsageError):
                prv.parse_pr_url(url)

    def test_remote_repo(self):
        cases = [
            ("https://github.com/CUBRID/CUBRID", "cubrid/cubrid"),
            ("https://github.com/CUBRID/cubrid.git", "cubrid/cubrid"),
            ("https://user@github.com/vimkim/cubrid/", "vimkim/cubrid"),
            ("git@github.com:vimkim/cubrid.git", "vimkim/cubrid"),
            ("ssh://git@github.com/vimkim/my.repo.git", "vimkim/my.repo"),
            ("https://gitlab.com/CUBRID/cubrid", None),
            ("/srv/git/cubrid.git", None),
        ]
        for url, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(prv.remote_repo(url), expected)

    def test_viewer_commands(self):
        self.assertEqual(prv.viewer_commands("nvim", "mb", "refs/prv/7/head", "src/a.c", "-W"),
                         [["nvim", "-c", "DiffviewOpen mb..refs/prv/7/head --selected-file=src/a.c"]])
        self.assertEqual(prv.viewer_commands("nvim", "mb", "h", None, "-W"),
                         [["nvim", "-c", "DiffviewOpen mb..h"]])
        self.assertEqual(prv.viewer_commands("nav", "mb", "h", "src/a.c", "-U9"),
                         [["git", "diff", "--no-color", "-U9", "mb", "h", "--", "src/a.c"],
                          ["diffnav"]])
        self.assertEqual(prv.viewer_commands("delta", "mb", "h", None, "-U9"),
                         [["git", "diff", "--no-color", "-U9", "mb", "h"], ["delta"]])


class CliTests(unittest.TestCase):
    """Run the deployed script against a fake gh and a local stand-in for GitHub."""

    URL = "https://github.com/Owner/Repo/pull/7"

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.calls = self.root / "gh-calls.jsonl"
        upstream = self.root / "upstream.git"
        self.env = {**os.environ,
                    "PATH": f"{self.root}{os.pathsep}{os.environ['PATH']}",
                    "GH_CALLS": str(self.calls),
                    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CEILING_DIRECTORIES": str(self.root.parent),
                    # Fetches from the GitHub URL go to the local bare repository.
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": f"url.{upstream}.insteadOf",
                    "GIT_CONFIG_VALUE_0": "https://github.com/Owner/Repo",
                    "GIT_AUTHOR_NAME": "Test", "GIT_COMMITTER_NAME": "Test",
                    "GIT_AUTHOR_EMAIL": "test@example.org",
                    "GIT_COMMITTER_EMAIL": "test@example.org"}
        self.env.pop("PRV_CONTEXT", None)
        gh = self.root / "gh"
        gh.write_text("#!/bin/sh\n"
                      "printf '%s\\n' \"$*\" >> \"$GH_CALLS\"\n"
                      "echo develop\n")
        gh.chmod(0o755)

        # Upstream history: develop advances after the PR branches off, so the
        # merge base differs from the base branch tip.
        work = self.root / "work"
        self.git(self.root, "init", "-q", "-b", "develop", str(work))
        self.commit(work, {"src/a.c": "one\n", "docs/b.md": "doc\n"}, "base")
        self.fork_point = self.git(work, "rev-parse", "HEAD")
        self.git(work, "switch", "-q", "-c", "topic")
        self.commit(work, {"src/a.c": "one\ntwo\n", "docs/b.md": "doc v2\n"}, "pr")
        self.pr_head = self.git(work, "rev-parse", "HEAD")
        self.git(work, "switch", "-q", "develop")
        self.commit(work, {"later.txt": "later\n"}, "after fork")
        self.git(self.root, "init", "-q", "--bare", str(upstream))
        self.git(work, "push", "-q", str(upstream), "develop", "topic:refs/pull/7/head")

        self.clone = self.root / "clone"
        self.git(self.root, "init", "-q", str(self.clone))
        self.git(self.clone, "remote", "add", "origin", "https://github.com/Owner/Repo")

    def git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, work, files, message):
        for name, text in files.items():
            (work / name).parent.mkdir(parents=True, exist_ok=True)
            (work / name).write_text(text)
        self.git(work, "add", "-A")
        self.git(work, "commit", "-q", "-m", message)

    def prv(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd or self.clone,
                              env=self.env, capture_output=True, text=True, timeout=30)

    def test_anchor_selects_file_and_diff_starts_at_merge_base(self):
        result = self.prv("-n", f"{self.URL}/changes#diff-{anchor('src/a.c')}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(shlex.split(result.stdout), [
            "nvim", "-c",
            f"DiffviewOpen {self.fork_point}..refs/prv/7/head --selected-file=src/a.c"])
        self.assertEqual(self.git(self.clone, "rev-parse", "refs/prv/7/head"), self.pr_head)
        self.assertEqual(self.calls.read_text().split(),
                         "pr view 7 -R Owner/Repo --json baseRefName -q .baseRefName".split())

    def test_pager_modes_use_whole_file_context(self):
        result = self.prv("-n", self.URL, "nav")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(),
                         f"git diff --no-color -U100000 {self.fork_point} refs/prv/7/head"
                         " | diffnav")
        self.env["PRV_CONTEXT"] = "-W"
        result = self.prv("-n", f"{self.URL}#diff-{anchor('docs/b.md')}", "delta")
        self.assertEqual(result.stdout.strip(),
                         f"git diff --no-color -W {self.fork_point} refs/prv/7/head"
                         " -- docs/b.md | delta")

    def test_unknown_anchor_falls_back_to_all_files(self):
        result = self.prv("-n", f"{self.URL}#diff-{anchor('missing.c')}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("--selected-file", result.stdout)
        self.assertIn("matches no changed file", result.stderr)

    def test_delta_mode_renders_the_whole_file(self):
        if shutil.which("delta") is None:
            self.skipTest("delta is not installed")
        result = self.prv(f"{self.URL}#diff-{anchor('src/a.c')}", "delta")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("one", result.stdout)
        self.assertIn("two", result.stdout)

    def test_input_errors_exit_2(self):
        result = self.prv("https://github.com/Owner/Repo/issues/7")
        self.assertEqual((result.returncode, "pull request URL" in result.stderr), (2, True))
        result = self.prv("https://github.com/Other/Repo/pull/7")
        self.assertEqual((result.returncode, "no remote" in result.stderr), (2, True))
        result = self.prv(self.URL, cwd=self.root)
        self.assertEqual((result.returncode, "inside a clone" in result.stderr), (2, True))
        self.assertEqual(self.prv().returncode, 2)
        self.assertFalse(self.calls.exists(), "gh must not run for rejected input")

    def test_prune_deletes_only_prv_refs(self):
        self.assertEqual(self.prv("-n", self.URL).returncode, 0)
        self.git(self.clone, "update-ref", "refs/keep/me", self.pr_head)
        result = self.prv("--prune")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deleted 2 refs", result.stderr)
        self.assertEqual(self.git(self.clone, "for-each-ref", "--format=%(refname)"),
                         "refs/keep/me")


if __name__ == "__main__":
    unittest.main()
