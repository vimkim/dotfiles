"""Run the Bash entry point with disposable homes/remotes and contained tools."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'private_dot_config/my-scripts/bin/executable_daily-update'
GIT = shutil.which('git')
JUST = shutil.which('just')
JQ = shutil.which('jq')
CHEZMOI = shutil.which('chezmoi')


@unittest.skipUnless(GIT and JUST and JQ, 'git, just and jq required')
class DailyUpdateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'commands'
        self.env = {
            'HOME': str(self.home), 'PATH': f'{self.bin}:/usr/bin:/bin',
            'XDG_CACHE_HOME': str(self.home / '.cache'),
            'XDG_CONFIG_HOME': str(self.home / '.config'),
            'XDG_STATE_HOME': str(self.home / '.local/state'),
            'CODEX_HOME': str(self.home / '.codex'),
            'CLAUDE_CONFIG_DIR': str(self.home / '.claude'),
            'npm_config_cache': str(self.home / '.npm'),
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
            'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 'test@example.invalid',
            'GIT_COMMITTER_NAME': 'Test', 'GIT_COMMITTER_EMAIL': 'test@example.invalid',
            'TEST_LOG': str(self.log), 'REAL_GIT': GIT,
        }
        for name in ('codex', 'claude', 'npx'):
            self.executable(name, f'printf "%s\\n" "{name} $*" >>"$TEST_LOG"\nexit "${{FAIL_{name.upper()}:-0}}"\n')
        self.executable('brew', 'exit 1\n')
        self.executable('gh', 'exit 1\n')
        self.executable('git', '''
printf 'git:%s\n' "$*" >>"$TEST_LOG"
case "$*" in
  *" status "*) [ "${FAIL_STATUS:-}" != "$2" ] || exit 9 ;;
  *" fetch "*) [ "${FAIL_FETCH:-}" != "$2" ] || exit 9 ;;
  *" merge --ff-only "*) [ "${FAIL_FF:-}" != "$2" ] || exit 9 ;;
esac
exec "$REAL_GIT" "$@"
''')
        self.executable('just', f'exec {JUST} "$@"\n')
        self.executable('jq', f'exec {JQ} "$@"\n')
        self.repos = {}
        self.tools = {}
        self.seeds = {}
        for name in ('my-skills', 'my-cubrid-skills', 'my-git-utils', 'herdr-next-to-current', 'html-serve', 'dirpick', 'cubrid-tc-chronicle'):
            remote = self.root / f'{name}.git'
            seed = self.root / f'{name}-seed'
            self.git(self.root, 'init', '--bare', '--initial-branch=main', str(remote))
            self.git(self.root, 'clone', str(remote), str(seed))
            (seed / 'revision').write_text('before')
            recipe = 'sync:\n    @printf "%s:%s\\n" "{{justfile_directory()}}" "$(cat revision)" >> "$TEST_LOG"\n    @exit "${SYNC_RESULT:-0}"\n'
            if name == 'dirpick':
                recipe = recipe.replace('SYNC_RESULT', 'DIRPICK_SYNC_RESULT')
            if name == 'cubrid-tc-chronicle':
                recipe = recipe.replace('SYNC_RESULT', 'CHRONICLE_SYNC_RESULT')
            (seed / 'justfile').write_text(recipe)
            self.git(seed, 'add', '.')
            self.git(seed, 'commit', '-m', 'initial')
            self.git(seed, 'push', '-u', 'origin', 'HEAD')
            repo = self.home / 'gh' / name
            self.git(self.root, 'clone', str(remote), str(repo))
            if name in ('herdr-next-to-current', 'html-serve', 'dirpick', 'cubrid-tc-chronicle'):
                official = f'https://github.com/vimkim/{name}.git'
                self.git(repo, 'config', f'url.{remote}.insteadOf', official)
                self.git(repo, 'config', 'remote.origin.url', official)
            (self.tools if name in ('my-git-utils', 'herdr-next-to-current', 'html-serve', 'dirpick', 'cubrid-tc-chronicle') else self.repos)[name] = repo
            self.seeds[name] = seed

        remote = self.root / 'dotfiles.git'
        seed = self.root / 'dotfiles-seed'
        self.git(self.root, 'init', '--bare', '--initial-branch=main', str(remote))
        self.git(self.root, 'clone', str(remote), str(seed))
        (seed / 'revision').write_text('before')
        self.git(seed, 'add', '.')
        self.git(seed, 'commit', '-m', 'initial')
        self.git(seed, 'push', '-u', 'origin', 'HEAD')
        self.dotfiles = self.home / 'configured dotfiles'
        self.git(self.root, 'clone', str(remote), str(self.dotfiles))
        official = 'https://github.com/vimkim/dotfiles.git'
        self.git(self.dotfiles, 'config', f'url.{remote}.insteadOf', official)
        self.git(self.dotfiles, 'config', 'remote.origin.url', official)
        self.seeds['dotfiles'] = seed
        self.env['TEST_DOTFILES'] = str(self.dotfiles)
        self.executable('chezmoi', '''
[ "$*" = source-path ] || exit 8
[ "${FAIL_SOURCE_PATH:-0}" = 0 ] || exit 9
printf '%s\n' "${TEST_SOURCE:-$TEST_DOTFILES}"
''')
        self.executable('chezmoi-apply-unmodified', '''
[ "$#" = 2 ] && [ "$1" = --source ] && [ "$2" = "$TEST_DOTFILES" ] || exit 8
printf 'dotfiles:%s\n' "$(cat "$2/revision")" >>"$TEST_LOG"
[ -z "${APPLY_OUTPUT:-}" ] || printf '%s\n' "$APPLY_OUTPUT"
exit "${FAIL_APPLY:-0}"
''')

    def executable(self, name, contents):
        path = self.bin / name
        path.write_text('#!/bin/bash\n' + contents)
        path.chmod(0o755)

    def git(self, repo, *args):
        return subprocess.run([GIT, '-C', str(repo), *args], env=self.env,
                              capture_output=True, text=True, check=True).stdout.strip()

    def run_daily(self, *args, **env):
        return subprocess.run(['bash', str(SCRIPT), *args], cwd=self.root,
                              env=self.env | env, text=True, capture_output=True)

    def logged(self):
        return self.log.read_text() if self.log.exists() else ''

    def advance(self, name):
        seed = self.seeds[name]
        (seed / 'revision').write_text('after')
        self.git(seed, 'commit', '-am', 'advance')
        self.git(seed, 'push')

    def lock(self, skills):
        path = self.home / '.agents/.skill-lock.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({'version': 3, 'skills': skills}))
        return path

    def assert_other_runs(self, result, bad, code):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        other = 'my-cubrid-skills' if bad == 'my-skills' else 'my-skills'
        self.assertIn(f'{self.repos[other]}:before', self.logged())
        self.assertNotIn(f'{self.repos[bad]}:', self.logged())

    def assert_dotfiles_skipped(self, result, code=2):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertNotIn('dotfiles:before', self.logged())
        self.assertNotIn('dotfiles:after', self.logged())
        self.assertIn('codex update', self.logged())
        self.assertIn(f"{self.repos['my-skills']}:before", self.logged())

    def test_dotfiles_refresh_and_apply_precede_upgrades_even_when_unchanged(self):
        self.advance('dotfiles')
        for _ in range(2):
            self.log.unlink(missing_ok=True)
            result = self.run_daily()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rows = self.logged().splitlines()
            self.assertLess(rows.index('dotfiles:after'), rows.index('codex update'))
            self.assertIn('dotfiles: completed', result.stdout)
            self.assertEqual(self.git(self.dotfiles, 'rev-parse', 'HEAD'),
                             self.git(self.seeds['dotfiles'], 'rev-parse', 'HEAD'))

    def test_dotfiles_dirty_work_is_preserved_without_fetch(self):
        self.advance('dotfiles')
        tip = self.git(self.dotfiles, 'rev-parse', 'origin/main')
        for kind in ('unstaged', 'staged', 'untracked'):
            with self.subTest(kind=kind):
                self.log.unlink(missing_ok=True)
                path = self.dotfiles / ('scratch' if kind == 'untracked' else 'revision')
                path.write_text('valuable')
                if kind == 'staged':
                    self.git(self.dotfiles, 'add', 'revision')
                before = self.git(self.dotfiles, 'status', '--porcelain')
                result = self.run_daily()
                self.assert_dotfiles_skipped(result)
                self.assertIn('dotfiles: skipped (dirty checkout)', result.stdout)
                self.assertEqual(before, self.git(self.dotfiles, 'status', '--porcelain'))
                self.assertEqual(path.read_text(), 'valuable')
                self.assertEqual(tip, self.git(self.dotfiles, 'rev-parse', 'origin/main'))
                if kind == 'untracked':
                    path.unlink()
                else:
                    self.git(self.dotfiles, 'restore', '--staged', '--worktree', 'revision')

    def test_dotfiles_ahead_and_diverged_skip_deployment(self):
        (self.dotfiles / 'local').write_text('valuable')
        self.git(self.dotfiles, 'add', '.')
        self.git(self.dotfiles, 'commit', '-m', 'local')
        tip = self.git(self.dotfiles, 'rev-parse', 'HEAD')
        for diverged in (False, True):
            with self.subTest(diverged=diverged):
                self.log.unlink(missing_ok=True)
                if diverged:
                    self.advance('dotfiles')
                result = self.run_daily()
                self.assert_dotfiles_skipped(result)
                self.assertIn('dotfiles: skipped (ahead or diverged checkout)', result.stdout)
                self.assertEqual(tip, self.git(self.dotfiles, 'rev-parse', 'HEAD'))

    def test_dotfiles_topic_detached_and_no_upstream_skip_before_fetch(self):
        self.advance('dotfiles')
        self.git(self.dotfiles, 'switch', '-c', 'topic')
        self.git(self.dotfiles, 'branch', '--set-upstream-to=origin/main')
        for state in ('topic', 'detached', 'no-upstream'):
            with self.subTest(state=state):
                self.log.unlink(missing_ok=True)
                if state == 'detached':
                    self.git(self.dotfiles, 'switch', '--detach')
                elif state == 'no-upstream':
                    self.git(self.dotfiles, 'switch', 'main')
                    self.git(self.dotfiles, 'branch', '--unset-upstream')
                result = self.run_daily()
                self.assert_dotfiles_skipped(result)
                self.assertIn('requires main tracking origin/main', result.stdout)
                self.assertNotIn(f'git:-C {self.dotfiles} fetch', self.logged())

    def test_dotfiles_unexpected_origin_is_preserved(self):
        self.git(self.dotfiles, 'remote', 'set-url', 'origin', 'https://example.invalid/other.git')
        result = self.run_daily()
        self.assert_dotfiles_skipped(result)
        self.assertIn('dotfiles: skipped (unexpected origin)', result.stdout)
        self.assertNotIn(f'git:-C {self.dotfiles} fetch', self.logged())

    def test_dotfiles_missing_or_nested_source_never_refreshes_parent(self):
        nested = self.dotfiles / 'nested'
        nested.mkdir()
        for source in (self.root / 'missing', nested):
            with self.subTest(source=source):
                self.log.unlink(missing_ok=True)
                result = self.run_daily(TEST_SOURCE=str(source))
                self.assert_dotfiles_skipped(result)
                self.assertIn('missing independent source checkout', result.stdout)
                self.assertNotIn(f'git:-C {source} fetch', self.logged())

    def test_dotfiles_failures_skip_apply_and_allow_other_updates(self):
        self.advance('dotfiles')
        for failure in ('FAIL_STATUS', 'FAIL_FETCH', 'FAIL_FF'):
            with self.subTest(failure=failure):
                self.log.unlink(missing_ok=True)
                tip = self.git(self.dotfiles, 'rev-parse', 'HEAD')
                result = self.run_daily(**{failure: str(self.dotfiles)})
                self.assert_dotfiles_skipped(result, code=1)
                self.assertIn('dotfiles: FAILED', result.stdout)
                self.assertEqual(tip, self.git(self.dotfiles, 'rev-parse', 'HEAD'))
        result = self.run_daily(FAIL_SOURCE_PATH='1')
        self.assert_dotfiles_skipped(result, code=1)
        self.assertIn('cannot locate configured source', result.stdout)

    def test_dotfiles_deleted_remote_main_never_uses_stale_tracking_ref(self):
        self.git(self.seeds['dotfiles'], 'config', 'remote.origin.receivepack',
                 'git -c receive.denyDeleteCurrent=ignore receive-pack')
        self.git(self.seeds['dotfiles'], 'push', 'origin', '--delete', 'main')
        result = self.run_daily()
        self.assert_dotfiles_skipped(result, code=1)
        self.assertIn('dotfiles: FAILED (fetch)', result.stdout)

    def test_dotfiles_apply_failure_is_reported_and_independent(self):
        result = self.run_daily(FAIL_APPLY='2', APPLY_OUTPUT='apply failed')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('dotfiles: FAILED (apply exit 2)', result.stdout)
        self.assertIn('apply failed', result.stdout)
        self.assertIn('claude update', self.logged())
        self.assertIn(f"{self.repos['my-skills']}:before", self.logged())
        self.assertEqual(self.run_daily('--remind').stdout, '')

    def test_dotfiles_helper_skips_are_partial_and_visible_in_summary(self):
        for message in ('Skipped locally changed target: /home/test/local',
                        'Skipped pre-existing target without last-write state: /home/test/local'):
            with self.subTest(message=message):
                result = self.run_daily(APPLY_OUTPUT=message)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn(message, result.stdout)
                self.assertIn('dotfiles: partial/skipped', result.stdout)
                self.assertIn('skipped: dotfiles', result.stdout)
                self.assertEqual(self.run_daily('--remind').stdout, '')

    def test_dotfiles_missing_helper_skips_and_non_run_modes_do_not_refresh(self):
        (self.bin / 'chezmoi-apply-unmodified').unlink()
        result = self.run_daily()
        self.assert_dotfiles_skipped(result)
        self.assertIn('requires chezmoi, git and chezmoi-apply-unmodified', result.stdout)
        self.log.unlink()
        for mode in ('--remind', '--status', '--help', '--stale', '--prune', '--reset'):
            result = self.run_daily(mode)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.logged(), '')

    @unittest.skipUnless(CHEZMOI, 'chezmoi required')
    def test_dotfiles_with_real_helper_updates_clean_targets_and_preserves_edits(self):
        seed = self.seeds['dotfiles']
        (seed / '.chezmoiignore').write_text('revision\n')
        for name in ('clean', 'dirty', 'deleted'):
            (seed / name).write_text('before')
        self.git(seed, 'add', '.')
        self.git(seed, 'commit', '-m', 'managed files')
        self.git(seed, 'push')
        self.git(self.dotfiles, 'pull', '--ff-only')
        dest = self.root / 'destination'
        dest.mkdir()
        config = self.root / 'chezmoi.json'
        config.write_text(json.dumps({
            'sourceDir': str(self.dotfiles), 'destDir': str(dest),
            'persistentState': str(self.root / 'state.boltdb'),
            'cacheDir': str(self.root / 'chezmoi-cache'),
        }))
        self.executable('chezmoi', f'exec {shlex.quote(CHEZMOI)} --config {shlex.quote(str(config))} "$@"\n')
        helper = SCRIPT.with_name('executable_chezmoi-apply-unmodified')
        self.executable('chezmoi-apply-unmodified', f'exec bash {shlex.quote(str(helper))} "$@"\n')
        subprocess.run([str(self.bin / 'chezmoi'), 'apply'], env=self.env,
                       check=True, capture_output=True, text=True)
        (dest / 'dirty').write_text('valuable')
        (dest / 'deleted').unlink()
        (dest / 'preexisting').write_text('valuable')
        for name in ('clean', 'dirty', 'deleted', 'preexisting'):
            (seed / name).write_text('after')
        self.git(seed, 'add', '.')
        self.git(seed, 'commit', '-m', 'update managed files')
        self.git(seed, 'push')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual((dest / 'clean').read_text(), 'after')
        self.assertEqual((dest / 'dirty').read_text(), 'valuable')
        self.assertFalse((dest / 'deleted').exists())
        self.assertEqual((dest / 'preexisting').read_text(), 'valuable')
        self.assertIn('dotfiles: partial/skipped', result.stdout)
        self.assertIn('skipped: dotfiles', result.stdout)

    def test_clean_refresh_before_sync_both_orders(self):
        for name in self.repos:
            self.advance(name)
        for order in ('', 'cubrid-first'):
            with self.subTest(order=order):
                self.log.unlink(missing_ok=True)
                result = self.run_daily(DAILY_UPDATE_COLLECTION_ORDER=order)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                rows = [row for row in self.logged().splitlines() if ':after' in row]
                expected = list(self.repos)
                if order:
                    expected.reverse()
                self.assertEqual(rows, [f'{self.repos[n]}:after' for n in expected])
                self.assertIn('codex update', self.logged())
                self.assertIn('claude update', self.logged())
                self.assertEqual(self.run_daily('--remind').stdout, '')
                self.assertIn('upkeep done', self.run_daily('--status').stdout)
        self.assertEqual(self.run_daily('--reset').returncode, 0)
        self.assertIn('pending', self.run_daily('--remind').stdout)

    def test_tool_checkout_refreshes_after_collections(self):
        self.advance('my-git-utils')
        result = self.run_daily()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = self.logged().splitlines()
        tool = rows.index(f"{self.tools['my-git-utils']}:after")
        self.assertGreater(tool, max(rows.index(f'{repo}:before') for repo in self.repos.values()))
        self.assertIn('tool:my-git-utils: completed', result.stdout)

    def test_chronicle_refreshes_and_syncs_cli_after_other_tools(self):
        self.advance('cubrid-tc-chronicle')
        repo = self.tools['cubrid-tc-chronicle']
        # Data collection is deliberately absent from daily upkeep.
        seed = self.seeds['cubrid-tc-chronicle']
        with (seed / 'justfile').open('a') as stream:
            stream.write('sync-data:\n    @exit 97\n')
        self.git(seed, 'add', 'justfile')
        self.git(seed, 'commit', '-m', 'separate data collection')
        self.git(seed, 'push')
        result = self.run_daily()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('tool:cubrid-tc-chronicle: completed', result.stdout)
        rows = self.logged().splitlines()
        self.assertGreater(rows.index(f'{repo}:after'),
                           rows.index(f"{self.tools['dirpick']}:before"))

    def test_chronicle_preserves_topic_wrong_origin_and_dirty_checkouts(self):
        repo = self.tools['cubrid-tc-chronicle']
        for scenario in ('topic', 'wrong-origin', 'dirty'):
            with self.subTest(scenario=scenario):
                if scenario == 'topic':
                    self.git(repo, 'switch', '-c', 'topic')
                    self.git(repo, 'branch', '--set-upstream-to=origin/main')
                elif scenario == 'wrong-origin':
                    self.git(repo, 'config', 'remote.origin.url', 'https://example.invalid/other.git')
                else:
                    (repo / 'scratch').write_text('valuable')
                before = self.git(repo, 'rev-parse', 'HEAD')
                result = self.run_daily()
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn('tool:cubrid-tc-chronicle: skipped', result.stdout)
                self.assertEqual(before, self.git(repo, 'rev-parse', 'HEAD'))
                self.assertNotIn(f'{repo}:', self.logged())
                if scenario == 'topic':
                    self.git(repo, 'switch', 'main')
                if scenario == 'wrong-origin':
                    self.git(repo, 'config', 'remote.origin.url',
                             'https://github.com/vimkim/cubrid-tc-chronicle.git')
        self.assertEqual((repo / 'scratch').read_text(), 'valuable')

    def test_chronicle_failure_is_reported_and_does_not_collect_data(self):
        result = self.run_daily(CHRONICLE_SYNC_RESULT='9')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('tool:cubrid-tc-chronicle: FAILED (sync exit 9)', result.stdout)
        self.assertIn('tool:dirpick: completed', result.stdout)

    def test_chronicle_deleted_remote_main_does_not_install_stale_code(self):
        remote = self.root / 'cubrid-tc-chronicle.git'
        self.git(remote, 'update-ref', '-d', 'refs/heads/main')
        result = self.run_daily()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('tool:cubrid-tc-chronicle: FAILED (fetch)', result.stdout)
        self.assertNotIn(f"{self.tools['cubrid-tc-chronicle']}:", self.logged())

    def test_herdr_clean_main_refreshes_and_installs(self):
        self.advance('herdr-next-to-current')
        result = self.run_daily()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"{self.tools['herdr-next-to-current']}:after", self.logged())

    def test_herdr_topic_and_unexpected_origin_are_preserved(self):
        repo = self.tools['herdr-next-to-current']
        self.git(repo, 'switch', '-c', 'topic')
        self.git(repo, 'branch', '--set-upstream-to=origin/main')
        before = self.git(repo, 'rev-parse', 'HEAD')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('requires primary main', result.stdout)
        self.assertNotIn(f'{repo}:', self.logged())
        self.assertEqual(before, self.git(repo, 'rev-parse', 'HEAD'))
        self.git(repo, 'switch', 'main')
        self.git(repo, 'config', 'remote.origin.url', 'https://example.invalid/occupied.git')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('unexpected origin', result.stdout)
        self.assertNotIn(f'{repo}:', self.logged())

    def test_herdr_linked_worktree_is_preserved(self):
        repo = self.tools['herdr-next-to-current']
        primary = self.root / 'primary-herdr'
        repo.rename(primary)
        self.git(primary, 'switch', '--detach')
        self.git(primary, 'worktree', 'add', str(repo), 'main')
        self.git(repo, 'branch', '--set-upstream-to=origin/main')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('requires primary main', result.stdout)
        self.assertNotIn(f'{repo}:', self.logged())

    def test_herdr_dirty_checkout_is_preserved(self):
        repo = self.tools['herdr-next-to-current']
        (repo / 'scratch').write_text('valuable')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('tool:herdr-next-to-current: skipped (dirty checkout)', result.stdout)
        self.assertNotIn(f'{repo}:', self.logged())
        self.assertEqual((repo / 'scratch').read_text(), 'valuable')

    def test_html_serve_clean_main_refreshes_and_installs(self):
        self.advance('html-serve')
        result = self.run_daily()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"{self.tools['html-serve']}:after", self.logged())

    def test_html_serve_topic_and_unexpected_origin_are_preserved(self):
        repo = self.tools['html-serve']
        self.git(repo, 'switch', '-c', 'topic')
        self.git(repo, 'branch', '--set-upstream-to=origin/main')
        before = self.git(repo, 'rev-parse', 'HEAD')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('requires primary main', result.stdout)
        self.assertNotIn(f'{repo}:', self.logged())
        self.assertEqual(before, self.git(repo, 'rev-parse', 'HEAD'))
        self.git(repo, 'switch', 'main')
        self.git(repo, 'config', 'remote.origin.url', 'https://example.invalid/occupied.git')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('unexpected origin', result.stdout)
        self.assertNotIn(f'{repo}:', self.logged())

    def test_html_serve_linked_worktree_is_preserved(self):
        repo = self.tools['html-serve']
        primary = self.root / 'primary-html-serve'
        repo.rename(primary)
        self.git(primary, 'switch', '--detach')
        self.git(primary, 'worktree', 'add', str(repo), 'main')
        self.git(repo, 'branch', '--set-upstream-to=origin/main')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('requires primary main', result.stdout)
        self.assertNotIn(f'{repo}:', self.logged())

    def test_html_serve_dirty_checkout_is_preserved(self):
        repo = self.tools['html-serve']
        (repo / 'scratch').write_text('valuable')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('tool:html-serve: skipped (dirty checkout)', result.stdout)
        self.assertNotIn(f'{repo}:', self.logged())
        self.assertEqual((repo / 'scratch').read_text(), 'valuable')

    def test_dirpick_refreshes_and_syncs_without_installer(self):
        repo = self.tools['dirpick']
        seed = self.seeds['dirpick']
        self.advance('dirpick')
        for _ in range(2):
            self.log.unlink(missing_ok=True)
            result = self.run_daily()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(f'{repo}:after', self.logged())
            self.assertIn('tool:dirpick: completed', result.stdout)
            self.assertEqual(self.git(repo, 'rev-parse', 'HEAD'),
                             self.git(seed, 'rev-parse', 'HEAD'))

    def test_dirpick_preserves_dirty_topic_wrong_origin_and_symlink(self):
        repo = self.tools['dirpick']
        (repo / 'scratch').write_text('valuable')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn(f'{repo}:', self.logged())
        self.assertEqual((repo / 'scratch').read_text(), 'valuable')
        (repo / 'scratch').unlink()
        self.git(repo, 'switch', '-c', 'topic')
        self.git(repo, 'branch', '--set-upstream-to=origin/main')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn(f'{repo}:', self.logged())
        self.git(repo, 'switch', 'main')
        self.git(repo, 'config', 'remote.origin.url', 'https://example.invalid/occupied.git')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('unexpected origin', result.stdout)
        self.assertNotIn(f'{repo}:', self.logged())
        self.git(repo, 'config', 'remote.origin.url', 'https://github.com/vimkim/dirpick.git')
        primary = self.root / 'primary-dirpick'
        repo.rename(primary)
        repo.symlink_to(primary, target_is_directory=True)
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn(f'{repo}:', self.logged())

    def test_dirpick_ahead_and_linked_worktrees_are_skipped(self):
        repo = self.tools['dirpick']
        (repo / 'revision').write_text('unpublished')
        self.git(repo, 'commit', '-am', 'local work')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn(f'{repo}:', self.logged())
        self.assertEqual((repo / 'revision').read_text(), 'unpublished')
        primary = self.root / 'primary-dirpick'
        repo.rename(primary)
        self.git(primary, 'switch', '--detach')
        self.git(primary, 'worktree', 'add', str(repo), 'main')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('requires primary main', result.stdout)
        self.assertNotIn(f'{repo}:', self.logged())

    def test_dirpick_fetch_merge_and_sync_failures_allow_other_steps(self):
        repo = self.tools['dirpick']
        self.advance('dirpick')
        for failure in ({'FAIL_FETCH': str(repo)}, {'FAIL_FF': str(repo)},
                        {'DIRPICK_SYNC_RESULT': '1'}):
            with self.subTest(failure=failure):
                self.log.unlink(missing_ok=True)
                result = self.run_daily(**failure)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('tool:dirpick: FAILED', result.stdout)
                self.assertIn('codex update', self.logged())
                self.assertIn(f"{self.repos['my-skills']}:before", self.logged())
                if 'DIRPICK_SYNC_RESULT' not in failure:
                    self.assertNotIn(f'{repo}:', self.logged())
        result = self.run_daily()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dirpick_missing_justfile_never_uses_parent_recipe(self):
        repo = self.tools['dirpick']
        seed = self.seeds['dirpick']
        self.git(seed, 'rm', 'justfile')
        self.git(seed, 'commit', '-m', 'missing recipe')
        self.git(seed, 'push')
        (repo.parent / 'justfile').write_text('sync:\n    @echo parent-recipe >> "$TEST_LOG"\n')
        result = self.run_daily()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('tool:dirpick: FAILED (missing local justfile)', result.stdout)
        self.assertNotIn('parent-recipe', self.logged())
        self.assertNotIn(f'{repo}:', self.logged())

    def test_dirpick_deleted_remote_main_never_installs_from_stale_ref(self):
        repo = self.tools['dirpick']
        remote = self.root / 'dirpick.git'
        self.git(remote, 'update-ref', '-d', 'refs/heads/main')
        result = self.run_daily()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('tool:dirpick: FAILED (fetch)', result.stdout)
        self.assertNotIn(f'{repo}:', self.logged())

    def test_dirty_tool_checkout_is_skipped(self):
        (self.tools['my-git-utils'] / 'scratch').write_text('wip')
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('tool:my-git-utils: skipped (dirty checkout)', result.stdout)
        self.assertNotIn(f"{self.tools['my-git-utils']}:", self.logged())
        self.assertIn(f"{self.repos['my-skills']}:before", self.logged())

    def test_dirty_staged_and_untracked_preserved(self):
        for name, staged in (('my-skills', False), ('my-cubrid-skills', True)):
            with self.subTest(name=name):
                path = self.repos[name] / 'local-work'
                path.write_text('valuable')
                if staged:
                    self.git(self.repos[name], 'add', 'local-work')
                before = self.git(self.repos[name], 'status', '--porcelain')
                result = self.run_daily()
                self.assert_other_runs(result, name, 2)
                self.assertIn('dirty checkout', result.stdout)
                self.assertEqual(before, self.git(self.repos[name], 'status', '--porcelain'))
                self.assertEqual(path.read_text(), 'valuable')
                if staged:
                    self.git(self.repos[name], 'reset', '--', 'local-work')
                path.unlink()
                self.log.unlink()

    def test_ahead_and_diverged_preserved(self):
        name = 'my-skills'
        repo = self.repos[name]
        (repo / 'local').write_text('valuable')
        self.git(repo, 'add', '.')
        self.git(repo, 'commit', '-m', 'local')
        tip = self.git(repo, 'rev-parse', 'HEAD')
        for diverged in (False, True):
            if diverged:
                self.advance(name)
            result = self.run_daily()
            self.assert_other_runs(result, name, 2)
            self.assertIn('ahead or diverged', result.stdout)
            self.assertEqual(tip, self.git(repo, 'rev-parse', 'HEAD'))

    def test_fetch_failure_isolated(self):
        name = 'my-skills'
        self.git(self.repos[name], 'remote', 'set-url', 'origin', str(self.root / 'missing'))
        self.assert_other_runs(self.run_daily(), name, 1)

    def test_fast_forward_failure_isolated(self):
        name = 'my-skills'
        self.advance(name)
        self.assert_other_runs(self.run_daily(FAIL_FF=str(self.repos[name])), name, 1)
        self.assertEqual((self.repos[name] / 'revision').read_text(), 'before')

    def test_sync_failure_and_partial_isolated_both_orders(self):
        for code in (1, 2):
            for order in ('', 'cubrid-first'):
                with self.subTest(code=code, order=order):
                    # just's own public exit code is the recipe's exit code.
                    self.executable('just', f'''if [ "$PWD" = "{self.repos['my-skills']}" ]; then exit {code}; fi
exec {JUST} "$@"
''')
                    result = self.run_daily(DAILY_UPDATE_COLLECTION_ORDER=order)
                    self.assert_other_runs(result, 'my-skills', code)
                    self.assertIn('partial/skipped' if code == 2 else 'FAILED', result.stdout)
                    self.log.unlink()

    def test_missing_detached_no_upstream(self):
        name = 'my-skills'
        repo = self.repos[name]
        self.git(repo, 'checkout', '--detach')
        self.assert_other_runs(self.run_daily(), name, 2)
        self.git(repo, 'checkout', '-')
        self.git(repo, 'branch', '--unset-upstream')
        self.assert_other_runs(self.run_daily(), name, 2)
        shutil.rmtree(repo)
        self.assert_other_runs(self.run_daily(), name, 2)

    def test_nested_directory_never_refreshes_parent_checkout(self):
        name = 'my-skills'
        shutil.rmtree(self.repos[name] / '.git')
        self.git(self.home / 'gh', 'init')
        result = self.run_daily()
        self.assert_other_runs(result, name, 2)
        self.assertIn('missing independent checkout', result.stdout)

    def test_failed_first_inventory_scan_both_orders(self):
        self.lock({'other': {'source': 'someone/third-party', 'sourceType': 'github'}})
        for order, first in (('', 'my-skills'), ('cubrid-first', 'my-cubrid-skills')):
            with self.subTest(order=order):
                self.executable('find', f'if [ "$1" = "{self.repos[first]}" ]; then exit 1; fi\nexec /usr/bin/find "$@"\n')
                result = self.run_daily(DAILY_UPDATE_COLLECTION_ORDER=order)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('invalid lock/source evidence', result.stdout)
                self.assertNotIn('npx', self.logged())
                self.assertEqual(self.run_daily('--prune', DAILY_UPDATE_COLLECTION_ORDER=order).returncode, 1)

    def test_current_personal_name_collision_excluded(self):
        skill = self.repos['my-skills'] / 'skills/collision'
        skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('personal source')
        self.lock({
            'collision': {'source': 'someone/third-party', 'sourceType': 'github'},
            'other': {'source': 'someone/third-party', 'sourceType': 'github'},
            'old-local': {'source': str(self.repos['my-cubrid-skills']), 'sourceType': 'local'},
        })
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('skills@1.7.0 update other --global --yes', self.logged())
        self.assertNotIn('update collision', self.logged())
        self.assertNotIn('old-local --global', self.logged())

    def test_personal_github_entries_protected_dirty_and_missing(self):
        lock = self.lock({
            'personal': {'source': 'vimkim/my-skills', 'sourceType': 'github'},
            'old-personal': {'source': 'https://github.com/vimkim/my-cubrid-skills.git', 'sourceType': 'github'},
            'other': {'source': 'someone/third-party', 'sourceType': 'github'},
        })
        store = self.home / '.agents/skills'
        for name in ('personal', 'old-personal', 'other'):
            (store / name).mkdir(parents=True)
            (store / name / 'SKILL.md').write_text('local edits')
        before = lock.read_bytes()
        (self.repos['my-skills'] / 'dirty').touch()
        shutil.rmtree(self.repos['my-cubrid-skills'])
        result = self.run_daily()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('skills@1.7.0 update other --global --yes', self.logged())
        self.assertNotIn('update personal', self.logged())
        self.assertEqual(before, lock.read_bytes())
        # Broken personal links must also stay outside legacy prune.
        claude = self.home / '.claude/skills'
        claude.mkdir(parents=True)
        (claude / 'personal').symlink_to('/missing-personal')
        result = self.run_daily('--prune')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((claude / 'personal').is_symlink())
        self.assertEqual((store / 'personal/SKILL.md').read_text(), 'local edits')
        self.assertEqual(before, lock.read_bytes())

    def test_personal_only_lock_never_calls_bulk_update(self):
        self.lock({'mine': {'source': 'vimkim/my-skills', 'sourceType': 'github'}})
        result = self.run_daily()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('npx', self.logged())

    def test_malformed_lock_prevents_update_and_prune(self):
        lock = self.lock({})
        lock.write_text('{broken')
        result = self.run_daily()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('invalid lock/source evidence', result.stdout)
        self.assertNotIn('npx', self.logged())
        self.assertEqual(self.run_daily('--prune').returncode, 1)
        self.assertEqual(lock.read_text(), '{broken')
        self.assertEqual(self.run_daily('--remind').stdout, '')


if __name__ == '__main__':
    unittest.main()
