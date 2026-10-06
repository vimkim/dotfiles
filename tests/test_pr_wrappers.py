"""Exercise deployed-wrapper behavior without deploying dotfiles or contacting GitHub."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'private_dot_config/my-scripts/bin'
URL = 'https://github.com/CUBRID/cubrid/pull/8095'


class PrWrappersTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = self.root / 'calls.jsonl'
        self.env = {**os.environ, 'PATH': str(self.root) + os.pathsep + os.environ['PATH'],
                    'PR_CALLS': str(self.calls), 'PR_RESULT': URL,
                    'XDG_CACHE_HOME': str(self.root / 'cache'),
                    'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1',
                    'GIT_AUTHOR_NAME': 'Test', 'GIT_COMMITTER_NAME': 'Test',
                    'GIT_AUTHOR_EMAIL': 'test@example.org', 'GIT_COMMITTER_EMAIL': 'test@example.org'}
        stub = self.root / 'gh-pr-info'
        stub.write_text('''#!/usr/bin/env python3
import json,os,sys
with open(os.environ['PR_CALLS'],'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
print(os.environ['PR_RESULT'])
sys.exit(int(os.environ.get('PR_EXIT', '0')))
''')
        stub.chmod(0o755)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'review-CBRD-27512-pr-8095')
        self.git('commit', '-q', '--allow-empty', '-m', 'fixture')
        self.git('remote', 'add', 'origin', 'https://github.com/CUBRID/cubrid.git')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, env=self.env,
                              capture_output=True, text=True, check=True).stdout.strip()

    def wrapper(self, name, *args):
        return subprocess.run(['bash', str(BIN / ('executable_' + name)), *args],
                              cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=10)

    def test_url_wrappers_forward_selectors_and_exit_status(self):
        for name in ('gh-pr-url', 'gh-pr-view'):
            result = self.wrapper(name, '8095', '--repo', 'CUBRID/cubrid')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), URL)
            self.assertEqual(json.loads(self.calls.read_text().splitlines()[-1]),
                             ['8095', '--repo', 'CUBRID/cubrid', '--json', 'url', '--jq', '.url'])
            self.env['PR_EXIT'] = '3'
            self.assertEqual(self.wrapper(name).returncode, 3)
            self.env.pop('PR_EXIT')

    def test_starship_keeps_background_refresh_and_open_filter(self):
        self.env['PR_RESULT'] = '8095'
        self.assertEqual(self.wrapper('starship-github-pr.sh').returncode, 0)
        deadline = time.monotonic() + 5
        caches = []
        while time.monotonic() < deadline:
            caches = list((self.root / 'cache/starship-github-pr').glob('*'))
            if any(p.read_text().strip() == '8095' and '.tmp.' not in p.name for p in caches):
                break
            time.sleep(0.02)
        self.assertTrue(caches)
        self.assertEqual(self.wrapper('starship-github-pr.sh').stdout.strip(), '8095')
        args = json.loads(self.calls.read_text().splitlines()[-1])
        self.assertEqual(args, ['--json', 'number,state', '--jq',
                                'select(.state == "OPEN") | .number'])
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)

    def test_rebase_lookup_keeps_existing_branch_guard(self):
        oid = self.git('rev-parse', 'HEAD')
        self.env['PR_RESULT'] = '\t'.join(['develop', 'CBRD-27512-pgbuf-interrupt-policy',
                                          oid, oid, URL, 'hornetmj/cubrid', '8095'])
        before = self.git('show-ref', '--heads')
        result = self.wrapper('git-rebase-pr.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local PR head branch 'CBRD-27512-pgbuf-interrupt-policy' was not found",
                      result.stderr)
        self.assertEqual(before, self.git('show-ref', '--heads'))
        self.assertEqual(self.git('branch', '--show-current'), 'review-CBRD-27512-pr-8095')
        self.assertEqual(json.loads(self.calls.read_text().splitlines()[-1])[0], '--json')


if __name__ == '__main__':
    unittest.main()
