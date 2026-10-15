"""Verify conflict skipping against real chezmoi state in a disposable destination."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'private_dot_config/my-scripts/bin/executable_chezmoi-apply-unmodified'
CHEZMOI = shutil.which('chezmoi')
BASH = shutil.which('bash')


@unittest.skipUnless(CHEZMOI and BASH, 'chezmoi and bash required')
class ChezmoiApplyUnmodifiedTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='chezmoi-apply-unmodified-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.destination = self.root / 'destination'
        self.source.mkdir()
        self.destination.mkdir()
        self.config = self.root / 'chezmoi.json'
        self.config.write_text(json.dumps({
            'destDir': str(self.destination),
            'persistentState': str(self.root / 'state.boltdb'),
            'cacheDir': str(self.root / 'cache'),
        }))
        self.options = ['--source', str(self.source), '--config', str(self.config)]

    def source_file(self, name, contents):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def applied_file(self, name, contents='original\n'):
        source = self.source_file(name, contents)
        target = self.destination / name
        subprocess.run([CHEZMOI, *self.options, 'apply', '--', str(target)],
                       capture_output=True, text=True, check=True, timeout=10)
        return source, target

    def run_wrapper(self, *args):
        return subprocess.run([BASH, str(SCRIPT), *self.options, *map(str, args)],
                              capture_output=True, text=True, timeout=10)

    def test_updates_clean_files_and_skips_local_changes(self):
        clean_source, clean = self.applied_file("clean file with 'quotes'")
        dirty_source, dirty = self.applied_file('dirty')
        deleted_source, deleted = self.applied_file('locally-deleted')
        for source in (clean_source, dirty_source, deleted_source):
            source.write_text('source update\n')
        dirty.write_text('local edit\n')
        deleted.unlink()
        self.source_file('preexisting', 'source version\n')
        preexisting = self.destination / 'preexisting'
        preexisting.write_text('local version\n')

        result = self.run_wrapper()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(clean.read_text(), 'source update\n')
        self.assertEqual(dirty.read_text(), 'local edit\n')
        self.assertFalse(deleted.exists())
        self.assertEqual(preexisting.read_text(), 'local version\n')
        for target in (dirty, deleted):
            self.assertIn(f'Skipped locally changed target: {target}', result.stdout)
        self.assertIn(f'Skipped pre-existing target without last-write state: {preexisting}',
                      result.stdout)
        self.assertEqual(self.run_wrapper().returncode, 0)

    def test_creates_nested_files_and_updates_only_clean_symlinks(self):
        self.source_file('new directory/nested file', 'new\n')
        self.source_file('symlink_clean-link', 'old-target\n')
        self.source_file('symlink_dirty-link', 'old-target\n')
        for name in ('clean-link', 'dirty-link'):
            subprocess.run([CHEZMOI, *self.options, 'apply', '--',
                            str(self.destination / name)], capture_output=True,
                           text=True, check=True, timeout=10)
            self.source_file('symlink_' + name, 'new-target\n')
        dirty = self.destination / 'dirty-link'
        dirty.unlink()
        dirty.symlink_to('local-target')

        result = self.run_wrapper()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / 'new directory/nested file').read_text(), 'new\n')
        self.assertEqual(os.readlink(self.destination / 'clean-link'), 'new-target')
        self.assertEqual(os.readlink(dirty), 'local-target')

    def test_explicit_target_does_not_apply_other_files(self):
        selected_source, selected = self.applied_file('selected')
        other_source, other = self.applied_file('other')
        selected_source.write_text('selected update\n')
        other_source.write_text('other update\n')

        result = self.run_wrapper('--', selected)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(selected.read_text(), 'selected update\n')
        self.assertEqual(other.read_text(), 'original\n')
        selected.write_text('local edit\n')
        result = self.run_wrapper('--', selected)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(selected.read_text(), 'local edit\n')
        self.assertEqual(other.read_text(), 'original\n')

    def test_does_not_run_scripts_and_succeeds_without_file_changes(self):
        marker = self.root / 'script-ran'
        self.source_file('run_before_marker.sh', f'#!/bin/sh\ntouch "{marker}"\n')
        self.source_file('new-file', 'new\n')

        result = self.run_wrapper()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / 'new-file').read_text(), 'new\n')
        self.assertEqual(self.run_wrapper().returncode, 0)
        self.assertFalse(marker.exists())

    def test_failed_scan_does_not_apply_any_files(self):
        source, target = self.applied_file('clean')
        source.write_text('source update\n')
        self.source_file('broken.tmpl', '{{ nonexistent_template_function }}\n')

        result = self.run_wrapper()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), 'original\n')
        self.assertIn('nonexistent_template_function', result.stderr)

    def test_unparseable_filename_fails_before_applying(self):
        source, target = self.applied_file('clean')
        source.write_text('source update\n')
        for name in ('name\nwith-newline', 'trailing-newline\n'):
            with self.subTest(name=name):
                invalid_source = self.source_file(name, 'new\n')
                result = self.run_wrapper()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(target.read_text(), 'original\n')
                self.assertIn('unexpected status output', result.stderr)
                invalid_source.unlink()

    def test_rejects_relative_targets_and_force(self):
        source, target = self.applied_file('clean')
        source.write_text('source update\n')
        for args in (('--', 'clean'), ('--force',), ('--source',)):
            with self.subTest(args=args):
                result = self.run_wrapper(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(target.read_text(), 'original\n')


if __name__ == '__main__':
    unittest.main()
