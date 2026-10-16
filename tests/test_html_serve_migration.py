"""Verify bootstrap safeguards and legacy compatibility in disposable homes."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / '.chezmoiscripts/run_once_before_install-html-serve.sh'
SCRIPTS = ROOT / 'private_dot_config/my-scripts/bin'
GIT = shutil.which('git')
CHEZMOI = shutil.which('chezmoi')
ORIGIN = 'https://github.com/vimkim/html-serve.git'


@unittest.skipUnless(GIT, 'git required')
class HtmlServeMigration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home with spaces"
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'install.log'
        self.env = {
            **os.environ, 'HOME': str(self.home),
            'PATH': f'{self.bin}:/usr/bin:/bin',
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': str(self.root / 'gitconfig'),
            'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 'test@example.invalid',
            'GIT_COMMITTER_NAME': 'Test', 'GIT_COMMITTER_EMAIL': 'test@example.invalid',
            'TEST_INSTALL_LOG': str(self.log),
        }
        self.checkout = self.home / 'gh/html-serve'
        self.checkout.mkdir(parents=True)
        self.git(self.checkout, 'init', '--initial-branch=main')
        self.assets = self.checkout / 'src/html_serve/assets'
        (self.assets / 'vendor/chunks').mkdir(parents=True)
        (self.assets / 'viewer.html').write_text('viewer')
        (self.assets / 'vendor/chunks/diagram.js').write_text('diagram')
        (self.checkout / 'justfile').write_text('sync:\n    true\n')
        self.git(self.checkout, 'add', '.')
        self.git(self.checkout, 'commit', '-m', 'fixture')
        self.git(self.checkout, 'remote', 'add', 'origin', ORIGIN)
        self.legacy = self.home / '.config/my-scripts/share/serve-html'
        self.backup = self.home / '.local/state/html-serve/legacy-assets'
        self.stub('uv', 'exit 0\n')
        self.stub('just', 'printf "%s\\n" "$*" >> "$TEST_INSTALL_LOG"\nexit "${FAIL_INSTALL:-0}"\n')
        self.stub('chezmoi', 'printf "%s\\n" /test/dotfiles\n')

    def git(self, cwd, *args):
        return subprocess.run([GIT, '-C', str(cwd), *args], env=self.env,
                              capture_output=True, text=True, check=True).stdout.strip()

    def stub(self, name, body):
        target = self.bin / name
        target.write_text('#!/bin/bash\n' + body)
        target.chmod(0o755)

    def run_bootstrap(self, **env):
        return subprocess.run(['bash', str(BOOTSTRAP)], env=self.env | env,
                              capture_output=True, text=True)

    def seed_legacy(self):
        shutil.copytree(self.assets, self.legacy)

    def test_matching_assets_are_backed_up_and_rerun_is_safe(self):
        self.seed_legacy()
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.legacy.exists())
        self.assertEqual((self.backup / 'viewer.html').read_text(), 'viewer')
        self.assertIn('backed up unchanged', result.stdout)
        self.assertIn(str(self.checkout / 'justfile'), self.log.read_text())
        self.legacy.symlink_to(self.assets)
        self.assertEqual(self.run_bootstrap().returncode, 0)
        self.assertEqual(self.legacy.resolve(), self.assets)

    def test_modified_assets_extra_files_and_symlinks_are_preserved(self):
        for kind in ('edit', 'extra', 'symlink'):
            with self.subTest(kind=kind):
                self.seed_legacy()
                if kind == 'edit':
                    (self.legacy / 'viewer.html').write_text('local edit')
                elif kind == 'extra':
                    (self.legacy / 'personal.txt').write_text('valuable')
                else:
                    (self.legacy / 'personal').symlink_to(self.assets / 'viewer.html')
                result = self.run_bootstrap()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('preserved locally changed', result.stdout)
                self.assertTrue(self.legacy.is_dir())
                self.assertFalse(self.backup.exists())
                shutil.rmtree(self.legacy)

    def test_existing_backup_and_unexpected_symlink_are_preserved(self):
        self.seed_legacy()
        self.backup.mkdir(parents=True)
        (self.backup / 'valuable').write_text('saved')
        self.assertIn('backup path already exists', self.run_bootstrap().stdout)
        self.assertTrue(self.legacy.is_dir())
        shutil.rmtree(self.legacy)
        self.legacy.symlink_to(self.root)
        self.assertIn('unexpected legacy asset symlink', self.run_bootstrap().stdout)
        self.assertEqual(self.legacy.resolve(), self.root)

    def test_dirty_topic_and_unexpected_origin_do_not_install(self):
        (self.checkout / 'local-work').write_text('valuable')
        self.assertIn('dirty checkout', self.run_bootstrap().stderr)
        self.assertFalse(self.log.exists())
        (self.checkout / 'local-work').unlink()
        self.git(self.checkout, 'switch', '-c', 'topic')
        self.assertIn('not on main', self.run_bootstrap().stderr)
        self.assertFalse(self.log.exists())
        self.git(self.checkout, 'switch', 'main')
        self.git(self.checkout, 'remote', 'set-url', 'origin', 'https://example.invalid/other.git')
        self.assertIn('unexpected origin', self.run_bootstrap().stderr)
        self.assertFalse(self.log.exists())

    def test_linked_checkout_does_not_install(self):
        primary = self.root / 'primary'
        self.checkout.rename(primary)
        self.git(primary, 'switch', '--detach')
        self.git(primary, 'worktree', 'add', str(self.checkout), 'main')
        self.assertIn('linked worktree', self.run_bootstrap().stderr)
        self.assertFalse(self.log.exists())

    def test_failed_install_keeps_legacy_assets(self):
        self.seed_legacy()
        result = self.run_bootstrap(FAIL_INSTALL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('installation failed', result.stderr)
        self.assertTrue(self.legacy.is_dir())
        self.assertFalse(self.backup.exists())

    def test_failed_state_transition_restores_legacy_assets(self):
        self.seed_legacy()
        self.stub('chezmoi', 'exit 1\n')
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.legacy / 'viewer.html').read_text(), 'viewer')
        self.assertFalse(self.backup.exists())

    def test_missing_checkout_is_cloned_from_main(self):
        seed = self.root / 'seed'
        self.checkout.rename(seed)
        self.git(self.root, 'config', '--global', f'url.{seed}.insteadOf', ORIGIN)
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git(self.checkout, 'branch', '--show-current'), 'main')
        self.assertEqual(self.git(self.checkout, 'config', '--get', 'remote.origin.url'), ORIGIN)

    @unittest.skipUnless(CHEZMOI, 'chezmoi required')
    def test_helper_applies_directory_to_symlink_cutover(self):
        self.verify_cutover()

    @unittest.skipUnless(CHEZMOI, 'chezmoi required')
    def test_standard_apply_preserves_legacy_with_direct_migration_hint(self):
        self.verify_cutover(with_script=True)

    def verify_cutover(self, with_script=False):
        source = self.root / 'dotfiles'
        old = source / 'private_dot_config/my-scripts/share/serve-html'
        shutil.copytree(self.assets, old)
        config = self.root / 'chezmoi.json'
        config.write_text(json.dumps({
            'destDir': str(self.home), 'persistentState': str(self.root / 'state.boltdb'),
            'cacheDir': str(self.root / 'cache'),
        }))
        options = ['--source', str(source), '--config', str(config)]
        applied = subprocess.run([CHEZMOI, *options, 'apply', '--parent-dirs', '--', str(self.legacy)],
                                 env=self.env, capture_output=True, text=True)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        shutil.rmtree(old)
        (old.parent / 'symlink_serve-html').write_text(str(self.assets) + '\n')
        # Route bootstrap's state transition and helper commands to this fixture.
        self.stub('chezmoi', 'exec ' + shlex.join([CHEZMOI, *options]) + ' "$@"\n')
        if with_script:
            scripts = source / '.chezmoiscripts'
            scripts.mkdir()
            shutil.copy2(BOOTSTRAP, scripts / BOOTSTRAP.name)
            result = subprocess.run([CHEZMOI, *options, 'apply', '--parent-dirs'],
                                    env=self.env, capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Run the bootstrap script directly', result.stderr)
            self.assertTrue(self.legacy.is_dir())
            self.assertFalse(self.backup.exists())
            shutil.rmtree(scripts)
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        helper = SCRIPTS / 'executable_chezmoi-apply-unmodified'
        result = subprocess.run(['bash', str(helper), *options], env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.legacy.is_symlink(), result.stdout)
        self.assertEqual(self.legacy.resolve(), self.assets)
        result = subprocess.run([CHEZMOI, *options, 'diff', '--', str(self.legacy)],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')

    def test_both_legacy_wrappers_preserve_arguments_and_exit_status(self):
        target = self.home / '.local/bin/html-serve'
        target.parent.mkdir(parents=True)
        target.write_text(f'#!{sys.executable}\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\nsys.exit(7)\n')
        target.chmod(0o755)
        args = ['a path with spaces', "quote's #?.md", '--bind', '127.0.0.1']
        for command in (['sh', str(SCRIPTS / 'executable_html-serve')],
                        [sys.executable, str(SCRIPTS / 'executable_serve-html.py')]):
            with self.subTest(command=command):
                result = subprocess.run(command + args, env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 7, result.stderr)
                self.assertEqual(json.loads(result.stdout), args)


if __name__ == '__main__':
    unittest.main()
