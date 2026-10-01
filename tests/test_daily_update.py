"""Run the Bash entry point with disposable homes/remotes and contained tools."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'private_dot_config/my-scripts/bin/executable_daily-update'
GIT = shutil.which('git')
JUST = shutil.which('just')
JQ = shutil.which('jq')


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
case "$*" in
  *" merge --ff-only "*) [ "${FAIL_FF:-}" != "$2" ] || exit 9 ;;
esac
exec "$REAL_GIT" "$@"
''')
        self.executable('just', f'exec {JUST} "$@"\n')
        self.executable('jq', f'exec {JQ} "$@"\n')
        self.repos = {}
        self.seeds = {}
        for name in ('my-skills', 'my-cubrid-skills'):
            remote = self.root / f'{name}.git'
            seed = self.root / f'{name}-seed'
            self.git(self.root, 'init', '--bare', str(remote))
            self.git(self.root, 'clone', str(remote), str(seed))
            (seed / 'revision').write_text('before')
            (seed / 'justfile').write_text('sync:\n    @printf "%s:%s\\n" "{{justfile_directory()}}" "$(cat revision)" >> "$TEST_LOG"\n    @exit "${SYNC_RESULT:-0}"\n')
            self.git(seed, 'add', '.')
            self.git(seed, 'commit', '-m', 'initial')
            self.git(seed, 'push', '-u', 'origin', 'HEAD')
            repo = self.home / 'gh' / name
            self.git(self.root, 'clone', str(remote), str(repo))
            self.repos[name] = repo
            self.seeds[name] = seed

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
