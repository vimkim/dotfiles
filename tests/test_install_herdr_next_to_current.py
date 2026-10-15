"""Bootstrap checks use temporary homes and real Git; no network/install."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.chezmoiscripts/run_once_after_install-herdr-next-to-current.sh'
OFFICIAL = 'https://github.com/vimkim/herdr-next-to-current.git'
CHEZMOI = shutil.which('chezmoi')


class Bootstrap(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.checkout = self.home / 'gh/herdr-next-to-current'
        self.log = self.root / 'installed'
        self.env = dict(os.environ, HOME=str(self.home), PATH=f'{self.bin}:/usr/bin:/bin',
                        GIT_CONFIG_GLOBAL=str(self.home / '.gitconfig'), GIT_CONFIG_NOSYSTEM='1',
                        GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid',
                        GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid')
        for name in ('uv', 'just'):
            path = self.bin / name
            path.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{self.log}"\nexit "${{INSTALL_RESULT:-0}}"\n')
            path.chmod(0o755)
        self.seed = self.root / 'seed'
        self.git(self.root, 'init', '--initial-branch=main', str(self.seed))
        (self.seed / 'justfile').write_text('sync:\n    @true\n')
        self.git(self.seed, 'add', '.')
        self.git(self.seed, 'commit', '-m', 'initial')
        self.git(self.root, 'config', '--global', f'url.{self.seed}.insteadOf', OFFICIAL)

    def git(self, cwd, *args):
        return subprocess.run(['git', '-C', str(cwd), *args], env=self.env,
                              capture_output=True, text=True, check=True).stdout.strip()

    def run_bootstrap(self, **extra):
        return subprocess.run(['bash', str(SCRIPT)], env=self.env | extra,
                              capture_output=True, text=True)

    def test_fresh_and_existing_checkout_install_primary_main(self):
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git(self.checkout, 'branch', '--show-current'), 'main')
        self.assertIn(str(self.checkout / 'justfile'), self.log.read_text())
        self.log.unlink()
        self.assertEqual(self.run_bootstrap().returncode, 0)
        self.assertTrue(self.log.exists())

    def test_occupied_path_is_preserved_and_retryable(self):
        self.checkout.parent.mkdir(parents=True)
        self.checkout.write_text('valuable')
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('chezmoi apply', result.stderr)
        self.assertEqual(self.checkout.read_text(), 'valuable')
        self.assertFalse(self.log.exists())

    def test_dirty_topic_and_wrong_origin_are_not_installed(self):
        self.assertEqual(self.run_bootstrap().returncode, 0)
        self.log.unlink()
        (self.checkout / 'scratch').write_text('valuable')
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('dirty checkout', result.stderr)
        self.assertFalse(self.log.exists())
        (self.checkout / 'scratch').unlink()
        self.git(self.checkout, 'switch', '-c', 'topic')
        self.assertNotEqual(self.run_bootstrap().returncode, 0)
        self.git(self.checkout, 'switch', 'main')
        self.git(self.checkout, 'config', 'remote.origin.url', 'https://example.invalid/occupied.git')
        self.assertNotEqual(self.run_bootstrap().returncode, 0)
        self.assertFalse(self.log.exists())

    def test_missing_dependencies_and_failed_install_remain_retryable(self):
        (self.bin / 'uv').unlink()
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.checkout.exists())
        shutil.copy(self.bin / 'just', self.bin / 'uv')
        result = self.run_bootstrap(INSTALL_RESULT='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('installation failed', result.stderr)
        self.assertEqual(self.run_bootstrap().returncode, 0)

    def test_linked_worktree_is_preserved(self):
        self.checkout.parent.mkdir(parents=True)
        self.git(self.seed, 'worktree', 'add', '--detach', str(self.checkout), 'HEAD')
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('linked worktree', result.stderr)
        self.assertFalse(self.log.exists())

    @unittest.skipUnless(CHEZMOI, 'chezmoi required')
    def test_real_chezmoi_retries_failed_run_once_then_records_success(self):
        source = self.root / 'dotfiles'
        scripts = source / '.chezmoiscripts'
        scripts.mkdir(parents=True)
        shutil.copy(SCRIPT, scripts / SCRIPT.name)
        self.checkout.parent.mkdir(parents=True)
        self.checkout.write_text('valuable')
        command = [CHEZMOI, '--source', str(source), '--destination', str(self.home),
                   '--config', str(self.root / 'chezmoi.toml'), '--persistent-state',
                   str(self.root / 'state.boltdb'), '--no-tty', 'apply']
        result = subprocess.run(command, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())
        self.assertEqual(self.checkout.read_text(), 'valuable')
        self.checkout.unlink()
        result = subprocess.run(command, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.log.exists())
        self.log.unlink()
        result = subprocess.run(command, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.log.exists())
