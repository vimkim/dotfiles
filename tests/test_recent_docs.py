import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCES = Path(__file__).resolve().parents[1] / "private_dot_config/my-scripts/bin"
FD = shutil.which("fd")
FIND = shutil.which("find")
BACKENDS = ("find", "fd") if FD else ("find",)
BASE_NS = 1_700_000_000_000_000_000


class RecentDocsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="recent-docs-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.gh = self.home / "gh"
        self.temp = self.home / "temp"
        self.gh.mkdir(parents=True)
        self.temp.mkdir()
        self.cwd = self.home / "working directory"
        self.cwd.mkdir()
        self.installed = self.root / "installed"
        self.installed.mkdir()
        for name in ("recent-docs.sh", "recent-docs-gh"):
            shutil.copy2(SOURCES / ("executable_" + name), self.installed / name)
        self.script = self.installed / "recent-docs.sh"
        self.wrapper = self.installed / "recent-docs-gh"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "python3").symlink_to(sys.executable)
        (self.bin / "find").symlink_to(FIND)
        (self.bin / "bash").symlink_to("/bin/bash")

    def create_file(self, name, modified_ns=BASE_NS):
        path = self.home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
        os.utime(path, ns=(modified_ns, modified_ns))
        return path

    def run_script(self, backend, *directories, program=None, cwd=None):
        fd_link = self.bin / "fd"
        fd_link.unlink(missing_ok=True)
        if backend == "fd":
            fd_link.symlink_to(FD)
        env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin), TZ="UTC",
                   XDG_CONFIG_HOME=str(self.home / ".config"),
                   GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        return subprocess.run(
            [str(program or self.script), *map(str, directories)],
            env=env,
            cwd=cwd or self.cwd,
            text=True,
            capture_output=True,
            timeout=15,
        )

    def assert_success(self, result, backend):
        self.assertEqual(result.returncode, 0, result.stderr)
        warning = "Warning: fd is not installed; using find instead.\n"
        self.assertEqual(result.stderr, warning if backend == "find" else "")

    @staticmethod
    def paths(result):
        return [line[18:] for line in result.stdout.splitlines()]

    def test_no_arguments_search_current_directory_only(self):
        selected = self.create_file("working directory/nested/local.md")
        self.create_file("gh/ignored.md", BASE_NS + 1)
        self.create_file("temp/ignored.html", BASE_NS + 2)
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend)
                self.assert_success(result, backend)
                self.assertEqual(self.paths(result), [str(selected)])

    def test_explicit_directories_search_both_and_filter_extensions(self):
        older = self.create_file("gh/older.md", BASE_NS)
        newer = self.create_file("temp/newer.HTML", BASE_NS + 1)
        self.create_file("gh/unrelated.txt", BASE_NS + 2)
        self.create_file("temp/not-markdown.mdx", BASE_NS + 3)
        (self.gh / "directory.md").mkdir()
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend, self.gh, self.temp)
                self.assert_success(result, backend)
                self.assertEqual(self.paths(result), [str(newer), str(older)])

    def test_returns_all_files_with_nanosecond_ordering(self):
        files = [
            self.create_file(f"gh/{i:02}.md", BASE_NS + i)
            for i in range(45)
        ]
        for backend in BACKENDS:
            for program in (self.script, self.wrapper):
                with self.subTest(backend=backend, program=program.name):
                    directories = (self.gh,) if program == self.script else ()
                    result = self.run_script(backend, *directories, program=program)
                    self.assert_success(result, backend)
                    self.assertEqual(self.paths(result), list(map(str, files[::-1])))

    def test_excludes_hidden_and_dependency_trees_without_ignore_files(self):
        selected = self.create_file("gh/selected.md")
        for name in (".hidden/hidden.MD", ".hidden.md", "node_modules/readme.md",
                     "nested/node_modules/readme.html"):
            self.create_file("gh/" + name, BASE_NS + 1)
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend, self.gh)
                self.assert_success(result, backend)
                self.assertEqual(self.paths(result), [str(selected)])

    def test_respects_each_ignore_file_outside_a_git_repository(self):
        for ignore_name in (".gitignore", ".ignore", ".fdignore"):
            with self.subTest(ignore_file=ignore_name):
                ignore = self.create_file("gh/" + ignore_name)
                ignore.write_text("ignored/\n")
                selected = self.create_file("gh/selected.md")
                self.create_file("gh/ignored/readme.md", BASE_NS + 1)
                for backend in BACKENDS:
                    with self.subTest(backend=backend):
                        result = self.run_script(backend, self.gh)
                        self.assert_success(result, backend)
                        self.assertEqual(self.paths(result), [str(selected)])
                ignore.unlink()

    def check_paths_on_both_backends(self, expected, *directories):
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend, *(directories or (self.gh,)))
                self.assert_success(result, backend)
                self.assertEqual(self.paths(result), list(map(str, expected)))

    def test_nested_rules_and_negation_for_each_ignore_file(self):
        for ignore_name in (".gitignore", ".ignore", ".fdignore"):
            with self.subTest(ignore_file=ignore_name):
                parent = self.create_file("gh/" + ignore_name)
                parent.write_text("*.md\nblocked/\n!blocked/keep.md\n")
                child = self.create_file("gh/docs/" + ignore_name)
                child.write_text("!keep.md\n")
                selected = self.create_file("gh/docs/keep.md")
                self.create_file("gh/drop.md", BASE_NS + 1)
                self.create_file("gh/docs/drop.md", BASE_NS + 2)
                self.create_file("gh/blocked/keep.md", BASE_NS + 3)
                self.check_paths_on_both_backends([selected])
                parent.unlink()
                child.unlink()

    def test_directory_negation_can_reinclude_a_subtree(self):
        self.create_file("gh/.gitignore").write_text(
            "build/*\n!build/docs/\nbuild/docs/*.md\n!build/docs/keep.md\n"
        )
        selected = self.create_file("gh/build/docs/keep.md")
        self.create_file("gh/build/docs/drop.md", BASE_NS + 1)
        self.create_file("gh/build/other/drop.html", BASE_NS + 2)
        self.check_paths_on_both_backends([selected])

    def test_ignore_file_priority_overrides_depth(self):
        self.create_file("gh/.fdignore").write_text("!keep.md\ndrop.html\n")
        self.create_file("gh/docs/.ignore").write_text("keep.md\n!drop.html\n")
        self.create_file("gh/docs/.gitignore").write_text("*.md\n!drop.html\n")
        selected = self.create_file("gh/docs/keep.md")
        self.create_file("gh/docs/drop.html", BASE_NS + 1)
        self.check_paths_on_both_backends([selected])

    def test_ignore_rules_when_searching_multiple_repositories(self):
        self.create_file("gh/.gitignore").write_text("*.md\n")
        self.create_file("gh/.ignore").write_text("shared.html\n")
        selected = []
        for name in ("first", "second"):
            (self.gh / name / ".git").mkdir(parents=True)
            self.create_file(f"gh/{name}/.gitignore").write_text("generated/\n!keep.md\n")
            selected.append(self.create_file(f"gh/{name}/keep.md"))
            self.create_file(f"gh/{name}/generated/drop.md", BASE_NS + 1)
            self.create_file(f"gh/{name}/shared.html", BASE_NS + 2)
            self.create_file(f"gh/{name}/inherited.md", BASE_NS + 3)
        self.check_paths_on_both_backends(sorted(selected, reverse=True))

    def test_parent_ignore_files_apply_to_explicit_search_roots(self):
        self.create_file(".fdignore").write_text("drop.md\n")
        self.create_file("gh/drop.md", BASE_NS + 1)
        selected = self.create_file("gh/keep.md")
        self.check_paths_on_both_backends([selected])

    def test_ignore_globs_anchors_escapes_and_directory_only_rules(self):
        self.create_file("gh/.ignore").write_text(
            "# comment\n\n/root.md\n**/draft?.md\nreports/**/drop[0-9].html\n"
            "dir-only.md/\n\\#literal.md\n\\!literal.md\nstar\\*.md\n"
            "trailing.md   \nspace\\ .md\n"
        )
        excluded = ("root.md", "draft1.md", "docs/draftA.md",
                    "reports/drop1.html", "reports/a/b/drop2.html",
                    "dir-only.md/inside.md", "#literal.md", "!literal.md",
                    "star*.md", "trailing.md", "space .md")
        for name in excluded:
            self.create_file("gh/" + name, BASE_NS + 1)
        selected = [self.create_file("gh/" + name) for name in
                    ("docs/root.md", "draft12.md", "reports/dropx.html", "sub/dir-only.md")]
        self.check_paths_on_both_backends(sorted(selected, reverse=True))

    def test_caret_and_exclamation_bracket_negation(self):
        for prefix in ("^", "!"):
            with self.subTest(prefix=prefix):
                self.create_file("gh/.ignore").write_text(f"[{prefix}a].md\n")
                selected = self.create_file("gh/a.md")
                self.create_file("gh/b.md", BASE_NS + 1)
                self.check_paths_on_both_backends([selected])

    def test_find_reports_unsupported_extended_patterns(self):
        self.create_file("gh/1.md")
        for pattern in ("[[:digit:]].md", "{a,b}.md"):
            with self.subTest(pattern=pattern):
                self.create_file("gh/.ignore").write_text(pattern + "\n")
                result = self.run_script("find", self.gh)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("extended ignore patterns require fd", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_relative_roots_and_names_starting_with_a_dash(self):
        selected = self.create_file("working directory/-docs/selected.Md")
        self.check_paths_on_both_backends([selected], "-docs")

    def test_explicit_symlink_directory_root(self):
        selected = self.create_file("gh/keep.md")
        link = self.home / "linked"
        link.symlink_to(self.gh, target_is_directory=True)
        self.check_paths_on_both_backends([link / selected.name], link)

    def test_file_argument_returns_failure(self):
        regular_file = self.create_file("gh/keep.md")
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend, regular_file)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("not a directory", result.stderr)

    def test_explicit_directories_replace_current_directory(self):
        self.create_file("gh/default.md", BASE_NS + 1)
        self.create_file("working directory/ignored.md", BASE_NS + 2)
        selected = self.create_file("other/deep/selected.md", BASE_NS)
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend, self.home / "other")
                self.assert_success(result, backend)
                self.assertEqual(self.paths(result), [str(selected)])

    def test_gh_wrapper_searches_gh_and_ignores_temp_and_current_directory(self):
        selected = self.create_file("gh/nested/selected.md")
        self.create_file("temp/ignored.html", BASE_NS + 1)
        self.create_file("working directory/ignored.md", BASE_NS + 2)
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend, program=self.wrapper)
                self.assert_success(result, backend)
                self.assertEqual(self.paths(result), [str(selected)])

    def test_gh_wrapper_does_not_require_temp_directory(self):
        selected = self.create_file("gh/selected.md")
        self.temp.rmdir()
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend, program=self.wrapper)
                self.assert_success(result, backend)
                self.assertEqual(self.paths(result), [str(selected)])

    def test_gh_wrapper_can_be_invoked_with_a_relative_filename(self):
        selected = self.create_file("gh/selected.md")
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(
                    backend, program="./recent-docs-gh", cwd=self.installed
                )
                self.assert_success(result, backend)
                self.assertEqual(self.paths(result), [str(selected)])

    def test_empty_search_succeeds_without_output(self):
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend, self.gh)
                self.assert_success(result, backend)
                self.assertEqual(result.stdout, "")

    def test_missing_directory_returns_failure(self):
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend, self.home / "missing")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("missing", result.stderr)

    def test_does_not_follow_file_or_directory_symlinks(self):
        original = self.create_file("outside/target.md")
        (self.gh / "file.md").symlink_to(original)
        (self.gh / "directory").symlink_to(original.parent, target_is_directory=True)
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend, self.gh)
                self.assert_success(result, backend)
                self.assertEqual(result.stdout, "")

    def test_handles_spaces_unicode_and_escapes_control_characters(self):
        ordinary = self.create_file("gh/space 한글.md", BASE_NS)
        unusual = self.create_file("temp/line\nbreak\tback\\slash.md", BASE_NS + 1)
        escaped = str(unusual.parent) + r"/line\nbreak\tback\\slash.md"
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend, self.gh, self.temp)
                self.assert_success(result, backend)
                self.assertEqual(self.paths(result), [escaped, str(ordinary)])

    def test_equal_timestamps_have_deterministic_path_order(self):
        first = self.create_file("gh/a.md")
        last = self.create_file("gh/z.md")
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                result = self.run_script(backend, self.gh)
                self.assert_success(result, backend)
                self.assertEqual(self.paths(result), [str(last), str(first)])

    def test_timestamp_is_local_time_to_the_minute(self):
        self.create_file("gh/date.md", BASE_NS)
        expected = datetime.datetime.fromtimestamp(
            BASE_NS // 1_000_000_000, datetime.timezone.utc
        ).strftime("%Y-%m-%d %H:%M")
        result = self.run_script("find", self.gh)
        self.assert_success(result, "find")
        self.assertTrue(result.stdout.startswith(expected + "  "))

    def test_find_failure_is_reported_without_partial_output(self):
        find = self.bin / "find"
        find.unlink()
        find.write_text("#!/bin/bash\nprintf 'find failed\\n' >&2\nexit 17\n")
        find.chmod(0o755)
        result = self.run_script("find", self.gh)
        self.assertEqual(result.returncode, 17)
        self.assertIn("find failed", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_fd_failure_is_not_silently_retried_with_find(self):
        fd = self.bin / "fd"
        fd.write_text("#!/bin/bash\nprintf 'fd failed\\n' >&2\nexit 23\n")
        fd.chmod(0o755)
        result = subprocess.run(
            ["/bin/bash", str(self.script)],
            env=dict(os.environ, HOME=str(self.home), PATH=str(self.bin)),
            text=True,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 23)
        self.assertEqual(result.stderr, "fd failed\n")


if __name__ == "__main__":
    unittest.main()
