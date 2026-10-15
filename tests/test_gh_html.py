import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote


CLI = Path(__file__).resolve().parents[1] / "private_dot_config/my-scripts/bin/executable_gh-html"
SHA = "a" * 40


def run_cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(CLI), *map(str, args)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


class URLTests(unittest.TestCase):
    def test_github_and_raw_urls(self):
        cases = [
            ("https://github.com/alice/project/blob/main/reports/demo.html",
             "main/reports/demo.html"),
            ("https://github.com/alice/project/raw/main/reports/demo.html",
             "main/reports/demo.html"),
            ("https://raw.githubusercontent.com/alice/project/main/reports/demo.html",
             "main/reports/demo.html"),
            ("https://github.com/alice/project/blob/feature/report/demo.html",
             "feature/report/demo.html"),
            ("https://github.com/alice/project/blob/feature%2Freport/demo.html",
             "feature%2Freport/demo.html"),
            ("https://github.com/alice/project/blob/main/report%20%231%25%3F.html?raw=true#chart",
             "main/report%20%231%25%3F.html#chart"),
        ]
        for source, tail in cases:
            with self.subTest(source=source):
                result = run_cli(source)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, f"https://raw.githack.com/alice/project/{tail}\n")
                self.assertEqual(result.stderr, "")

    def test_cdn_requires_a_commit_for_url_input(self):
        result = run_cli("--cdn", f"https://github.com/alice/project/blob/{SHA}/demo.html")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"https://rawcdn.githack.com/alice/project/{SHA}/demo.html\n")
        result = run_cli("--cdn", "https://github.com/alice/project/blob/main/demo.html")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("full commit SHA", result.stderr)

    def test_bad_urls_fail_without_a_traceback(self):
        for source in [
            "https://example.com/alice/project/blob/main/demo.html",
            "https://github.com/alice/project/tree/main",
            "https://raw.githubusercontent.com/alice/project/main",
            "https://github.com/alice/project/blob/main/../demo.html",
            "https://github.com/alice/project/blob/main/",
            "https://user:password@github.com/alice/project/blob/main/demo.html",
            "file:///tmp/demo.html",
        ]:
            with self.subTest(source=source):
                result = run_cli(source)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("gh-html:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_ref_is_only_for_local_paths(self):
        result = run_cli("--ref", "main", "https://github.com/alice/project/blob/main/demo.html")
        self.assertEqual(result.returncode, 1)
        self.assertIn("--ref applies to local paths", result.stderr)


class LocalPathTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.repository = self.directory / "repository"
        self.repository.mkdir()
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "CLI Test")
        self.git("config", "user.email", "cli-test@example.com")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", "/dev/null")
        self.git("remote", "add", "origin", "git@github.com:alice/project.git")
        self.file = self.repository / "reports" / "demo.html"
        self.file.parent.mkdir()
        self.file.write_text("<html>first version</html>\n")
        self.special = self.file.parent / "한글 report #1%?.html"
        self.special.write_text("<html>special filename</html>\n")
        self.git("add", "reports")
        self.git("commit", "-m", "Add reports")
        self.first_commit = self.git("rev-parse", "HEAD")
        self.file.write_text("<html>second version</html>\n")
        self.git("add", "reports/demo.html")
        self.git("commit", "-m", "Update report")
        self.commit = self.git("rev-parse", "HEAD")

    def git(self, *args):
        result = subprocess.run(
            ["git", "-C", str(self.repository), *args],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    def expected(self, filename="reports/demo.html", commit=None, cdn=False):
        host = "rawcdn.githack.com" if cdn else "raw.githack.com"
        return f"https://{host}/alice/project/{commit or self.commit}/{quote(filename)}\n"

    def test_absolute_path_from_outside_repository(self):
        before = self.git("status", "--porcelain=v1")
        result = run_cli(self.file, cwd=self.directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.expected())
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.git("status", "--porcelain=v1"), before)

    def test_relative_path_with_special_characters(self):
        relative = self.special.relative_to(self.repository)
        result = run_cli(relative, cwd=self.repository)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.expected(relative.as_posix()))

    def test_ssh_and_https_remotes(self):
        for remote in [
            "git@github.com:alice/project.git",
            "ssh://git@github.com/alice/project.git",
            "https://github.com/alice/project.git",
            "https://github.com/alice/project/",
        ]:
            with self.subTest(remote=remote):
                self.git("remote", "set-url", "origin", remote)
                result = run_cli(self.file)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, self.expected())

    def test_selecting_remote_revision_and_cdn(self):
        self.git("remote", "rename", "origin", "upstream")
        result = run_cli("--remote", "upstream", "--ref", "HEAD~1", "--cdn", self.file)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.expected(commit=self.first_commit, cdn=True))
        self.assertIn("the URL shows the committed version", result.stderr)

    def test_worktree_and_detached_head(self):
        worktree = self.directory / "linked-worktree"
        self.git("worktree", "add", "--detach", str(worktree), "HEAD")
        result = run_cli(worktree / "reports/demo.html", cwd=self.directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.expected())

    def test_dirty_file_prints_committed_link_and_stderr_notice(self):
        self.file.write_text("<html>uncommitted edits</html>\n")
        result = run_cli(self.file)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.expected())
        self.assertIn("the URL shows the committed version", result.stderr)

    def test_uncommitted_new_file_is_rejected(self):
        new_file = self.repository / "new.html"
        new_file.write_text("<html>new</html>\n")
        self.git("add", "new.html")
        result = run_cli(new_file)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("not committed", result.stderr)

    def test_dirty_filename_with_git_pathspec_characters(self):
        file = self.repository / "reports" / "chart[1].html"
        file.write_text("<html>committed</html>\n")
        self.git("add", "reports")
        self.git("commit", "-m", "Add chart")
        self.commit = self.git("rev-parse", "HEAD")
        file.write_text("<html>edited</html>\n")
        result = run_cli(file)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.expected("reports/chart[1].html"))
        self.assertIn("the URL shows the committed version", result.stderr)

    def test_invalid_local_inputs_and_revisions(self):
        outside = self.directory / "outside.html"
        outside.write_text("<html>outside</html>\n")
        for args, message in [
            ((self.repository / "missing.html",), "does not exist"),
            ((self.repository,), "Expected a file"),
            ((outside,), "inside a Git repository"),
            (("--ref", "unknown-revision", self.file), "Cannot resolve Git revision"),
            (("--remote", "missing", self.file), "was not found"),
        ]:
            with self.subTest(args=args):
                result = run_cli(*args)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn(message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_non_github_remote_is_rejected(self):
        self.git("remote", "set-url", "origin", "git@gitlab.com:alice/project.git")
        result = run_cli(self.file)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("must point to github.com", result.stderr)


if __name__ == "__main__":
    unittest.main()
