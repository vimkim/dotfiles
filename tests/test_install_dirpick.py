"""Exercise bootstrap, Cargo installation and Nu navigation in disposable homes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / 'private_dot_config/my-scripts/bin/executable_install-dirpick'
BOOTSTRAP = ROOT / '.chezmoiscripts/run_once_after_install-dirpick.sh'
MODULE = ROOT / 'private_dot_config/nushell/dirpick.nu'
OFFICIAL = 'https://github.com/vimkim/dirpick.git'
CHEZMOI = shutil.which('chezmoi')
CARGO = shutil.which('cargo')
JUST = shutil.which('just')
NU = shutil.which('nu')


@unittest.skipUnless(JUST, 'just required')
class InstallDirpick(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / 'home with spaces'
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.checkout = self.home / 'gh/dirpick'
        self.command = self.home / '.config/my-scripts/bin/install-dirpick'
        self.command.parent.mkdir(parents=True)
        shutil.copyfile(INSTALLER, self.command)
        self.command.chmod(0o755)
        self.log = self.root / 'cargo.log'
        self.env = {
            'HOME': str(self.home), 'PATH': f'{self.bin}:/usr/bin:/bin',
            'GIT_CONFIG_GLOBAL': str(self.home / '.gitconfig'), 'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 'test@example.invalid',
            'GIT_COMMITTER_NAME': 'Test', 'GIT_COMMITTER_EMAIL': 'test@example.invalid',
            'TEST_LOG': str(self.log),
        }
        cargo = self.bin / 'cargo'
        cargo.write_text('''#!/bin/bash
printf '%s\\n' "$*" >>"$TEST_LOG"
[ "$#" = 8 ] && [ "$1" = install ] && [ "$2" = --locked ] &&
    [ "$3" = --path ] && [ "$4" = . ] && [ "$5" = --root ] &&
    [ "$6" = "$HOME/.local" ] && [ "$7" = --bin ] && [ "$8" = dirpick ] || exit 9
[ "${INSTALL_RESULT:-0}" = 0 ] || exit 1
mkdir -p "$HOME/.local/bin"
printf '#!/bin/sh\\nprintf "dirpick 0.1.0\\\\n"\\n' >"$HOME/.local/bin/dirpick"
chmod +x "$HOME/.local/bin/dirpick"
''')
        cargo.chmod(0o755)
        (self.bin / 'just').symlink_to(JUST)
        self.seed = self.root / 'seed'
        self.git(self.root, 'init', '--initial-branch=main', str(self.seed))
        (self.seed / '.gitignore').write_text('/target/\n')
        (self.seed / 'Cargo.toml').write_text(
            '[package]\nname = "dirpick"\nversion = "0.1.0"\nedition = "2024"\n')
        (self.seed / 'Cargo.lock').write_text(
            'version = 4\n\n[[package]]\nname = "dirpick"\nversion = "0.1.0"\n')
        (self.seed / 'justfile').write_text(
            'sync:\n'
            '    cargo install --locked --path . --root "$HOME/.local" --bin dirpick\n'
            '    "$HOME/.local/bin/dirpick" --version\n')
        (self.seed / 'src').mkdir()
        (self.seed / 'src/main.rs').write_text('fn main() { println!("dirpick old"); }\n')
        self.git(self.seed, 'add', '.')
        self.git(self.seed, 'commit', '-m', 'initial')
        self.git(self.root, 'config', '--global', f'url.{self.seed}.insteadOf', OFFICIAL)

    def git(self, cwd, *args):
        return subprocess.run(['git', '-C', str(cwd), *args], env=self.env,
                              capture_output=True, text=True, check=True).stdout.strip()

    def install(self, **extra):
        return subprocess.run(['bash', str(BOOTSTRAP)], env=self.env | extra,
                              capture_output=True, text=True)

    def test_fresh_clone_install_and_reinstall_use_shared_path(self):
        for _ in range(2):
            result = self.install(CARGO_INSTALL_ROOT=str(self.root / 'wrong root'))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('dirpick 0.1.0', result.stdout)
            self.assertEqual(self.git(self.checkout, 'branch', '--show-current'), 'main')
        self.assertEqual(len(self.log.read_text().splitlines()), 2)
        self.assertFalse((self.root / 'wrong root').exists())

    def test_occupied_and_symlink_paths_are_preserved(self):
        self.checkout.parent.mkdir(parents=True)
        self.checkout.write_text('valuable')
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.checkout.read_text(), 'valuable')
        self.assertFalse(self.log.exists())
        self.checkout.unlink()
        self.checkout.symlink_to(self.seed, target_is_directory=True)
        self.assertNotEqual(self.install().returncode, 0)
        self.assertTrue(self.checkout.is_symlink())
        self.assertFalse(self.log.exists())

    def test_dirty_topic_detached_and_wrong_origin_do_not_install(self):
        self.assertEqual(self.install().returncode, 0)
        self.log.unlink()
        (self.checkout / 'scratch').write_text('valuable')
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual((self.checkout / 'scratch').read_text(), 'valuable')
        (self.checkout / 'scratch').unlink()
        self.git(self.checkout, 'switch', '-c', 'topic')
        self.assertNotEqual(self.install().returncode, 0)
        self.git(self.checkout, 'switch', '--detach')
        self.assertNotEqual(self.install().returncode, 0)
        self.git(self.checkout, 'switch', 'main')
        self.git(self.checkout, 'config', 'remote.origin.url', 'https://example.invalid/other.git')
        self.assertNotEqual(self.install().returncode, 0)
        self.assertFalse(self.log.exists())

    def test_linked_worktree_is_preserved(self):
        self.checkout.parent.mkdir(parents=True)
        self.git(self.seed, 'worktree', 'add', '--detach', str(self.checkout), 'HEAD')
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('linked worktree', result.stderr)
        self.assertFalse(self.log.exists())

    def test_cargo_home_fallback_and_missing_dependency_retry(self):
        fallback = self.home / '.cargo/bin/cargo'
        fallback.parent.mkdir(parents=True)
        (self.bin / 'cargo').rename(fallback)
        self.assertEqual(self.install().returncode, 0)
        self.log.unlink()
        fallback.unlink()
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('install Rust and Cargo first', result.stderr)
        self.assertIn('Retry after correcting it:', result.stderr)
        self.assertFalse(self.log.exists())

    def test_failed_build_retains_binary_and_retries(self):
        self.assertEqual(self.install().returncode, 0)
        binary = self.home / '.local/bin/dirpick'
        before = binary.read_bytes()
        result = self.install(INSTALL_RESULT='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(binary.read_bytes(), before)
        self.assertEqual(self.install().returncode, 0)

    def test_missing_just_or_local_recipe_reports_retry(self):
        (self.bin / 'just').unlink()
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('install just first', result.stderr)
        self.assertFalse(self.checkout.exists())
        (self.bin / 'just').symlink_to(JUST)
        self.assertEqual(self.install().returncode, 0)
        self.log.unlink()
        self.git(self.checkout, 'rm', 'justfile')
        self.git(self.checkout, 'commit', '-m', 'missing recipe')
        (self.checkout.parent / 'justfile').write_text('sync:\n    exit 0\n')
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing local justfile', result.stderr)
        self.assertIn('Retry after correcting it:', result.stderr)
        self.assertFalse(self.log.exists())

    @unittest.skipUnless(CHEZMOI, 'chezmoi required')
    def test_real_chezmoi_deploys_installer_and_retries_run_once(self):
        source = self.root / 'dotfiles'
        scripts = source / '.chezmoiscripts'
        scripts.mkdir(parents=True)
        shutil.copyfile(BOOTSTRAP, scripts / BOOTSTRAP.name)
        managed = source / 'private_dot_config/my-scripts/bin/executable_install-dirpick'
        managed.parent.mkdir(parents=True)
        shutil.copyfile(INSTALLER, managed)
        self.command.unlink()
        command = [CHEZMOI, '--source', str(source), '--destination', str(self.home),
                   '--config', str(self.root / 'chezmoi.toml'), '--persistent-state',
                   str(self.root / 'state.boltdb'), '--no-tty', 'apply']
        for fail in ('1', '0'):
            result = subprocess.run(command, env=self.env | {'INSTALL_RESULT': fail},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode == 0, fail == '0', result.stdout + result.stderr)
            self.assertTrue(self.command.is_file())
        self.log.unlink()
        result = subprocess.run(command, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.log.exists(), 'successful run-once must not reinstall on each apply')

    @unittest.skipUnless(CARGO, 'cargo required')
    def test_real_cargo_replaces_same_version_and_preserves_binary_on_build_failure(self):
        # Use the host toolchain, with installation/cache and source confined here.
        self.env['RUSTUP_HOME'] = os.environ.get('RUSTUP_HOME', str(Path.home() / '.rustup'))
        (self.bin / 'cargo').unlink()
        proxies = self.home / '.cargo/bin'
        proxies.mkdir(parents=True)
        (proxies / 'cargo').symlink_to(CARGO)
        (proxies / 'rustc').symlink_to(shutil.which('rustc'))
        binary = self.home / '.local/bin/dirpick'
        binary.parent.mkdir(parents=True)
        binary.write_text('valuable unowned command')
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual(binary.read_text(), 'valuable unowned command')
        binary.unlink()
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('dirpick old', subprocess.check_output([str(binary)], text=True))
        (self.checkout / 'src/main.rs').write_text('fn main() { println!("dirpick new"); }\n')
        self.git(self.checkout, 'commit', '-am', 'same-version update')
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('dirpick new', subprocess.check_output([str(binary)], text=True))
        before = binary.read_bytes()
        (self.checkout / 'src/main.rs').write_text('invalid rust\n')
        self.git(self.checkout, 'commit', '-am', 'broken build')
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual(binary.read_bytes(), before)


@unittest.skipUnless(NU, 'nu required')
class NushellDirpick(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.bin = self.home / 'bin'
        self.bin.mkdir()
        command = self.bin / 'dirpick'
        command.write_text('#!/bin/sh\nprintf "%s" "$ACTION"\nexit "${ACTION_EXIT:-0}"\n')
        command.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), PATH=f'{self.bin}:/usr/bin:/bin')

    def run_nu(self, code, **extra):
        return subprocess.run([NU, '--no-config-file', '-c', code], cwd=self.home,
                              env=self.env | extra, capture_output=True, text=True)

    def test_dp_changes_shell_directory_and_preserves_trailing_whitespace(self):
        destination = self.home / 'project with space\t\n'
        destination.mkdir()
        code = f'use {json.dumps(str(MODULE))} dp; dp; $env.PWD | to json --raw'
        result = self.run_nu(code, ACTION=json.dumps({'action': 'cd', 'path': str(destination)}))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), str(destination))

    def test_cancel_and_invalid_actions_preserve_pwd(self):
        code = (f'use {json.dumps(str(MODULE))} dp; '
                'let failed = (try { dp; false } catch { true }); '
                '{failed: $failed, pwd: $env.PWD} | to json --raw')
        for action, exit_code, failed in [('', '0', False), ('', '1', True),
                                        ('{"action":"cd","path":"relative"}', '0', True),
                                        ('{"action":"cd","path":"/","extra":1}', '0', True)]:
            with self.subTest(action=action, exit_code=exit_code):
                result = self.run_nu(code, ACTION=action, ACTION_EXIT=exit_code)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout), {'failed': failed, 'pwd': str(self.home)})

    def test_config_import_loads_dp_and_tolerates_absent_module(self):
        config = (ROOT / 'private_dot_config/nushell/config.nu').read_text()
        start = config.index('const dirpick_module =')
        end = config.index('use $dirpick_module *', start) + len('use $dirpick_module *')
        # Run the actual parser-time import stanza, including the missing-file case.
        code = config[start:end] + '\n(scope commands | where name == dp | length)'
        result = self.run_nu(code)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), '0')
        target = self.home / '.config/nushell/dirpick.nu'
        target.parent.mkdir(parents=True)
        shutil.copyfile(MODULE, target)
        result = self.run_nu(code)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), '1')


if __name__ == '__main__':
    unittest.main()
