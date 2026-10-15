# gh-html

Print a rendered [githack](https://raw.githack.com/) link for an HTML file that is
already on GitHub. Requires Python 3.9 or newer, plus Git for local paths. No
Python packages are needed.

```sh
gh-html /path/to/repository/reports/demo.html
gh-html ./reports/demo.html
gh-html 'https://github.com/alice/project/blob/main/reports/demo.html'
gh-html 'https://raw.githubusercontent.com/alice/project/main/reports/demo.html'
```

A local path automatically supplies the repository from its `origin` remote, the
file path from the repository root, and the full current commit SHA. This works
from outside the repository and from linked Git worktrees. HTTPS and SSH GitHub
remotes are supported. For example:

```text
https://raw.githack.com/alice/project/FULL_COMMIT_SHA/reports/demo.html
```

Local links identify a particular commit so teammates see the same version. A
GitHub URL preserves its revision; pass a URL containing `main` to follow that
branch. Spaces and other special characters in file paths are URL-encoded.
URL fragments are preserved, and GitHub interface query parameters are removed.

```sh
# Use the CDN host for a particular committed version.
gh-html --cdn ./reports/demo.html

# Select another local revision or Git remote.
gh-html --ref origin/main --remote upstream ./reports/demo.html

# For URL input, CDN mode requires a full 40-character commit SHA.
gh-html --cdn 'https://github.com/alice/project/blob/FULL_COMMIT_SHA/reports/demo.html'
```

For local paths, `--ref` always resolves to a commit SHA, even when it names a
branch or tag. The file must exist both locally and at that revision. A file with
uncommitted edits produces a notice on stderr; stdout still contains only the URL
for the committed version. An uncommitted new file produces an error.

The command only converts paths. It does not upload files, commit, push, access
the network, or open a browser. The commit must already be pushed to a public
GitHub repository; remote availability is not checked. CSS, JavaScript, images,
and other relative assets must also be available at the same revision. Local
symlinks are resolved to their target before selecting the repository and file.

Githack's development URLs cache briefly; CDN URLs cache by URL and should use a
commit SHA. The service currently presents a confirmation page before opening
HTML in a browser. See the [service documentation](https://raw.githack.com/).

Chezmoi manages the executable source at
`private_dot_config/my-scripts/bin/executable_gh-html` and deploys it to
`~/.config/my-scripts/bin/gh-html`, which is already on PATH.

Run the focused checks:

```sh
python3 -m unittest discover -s tests -p test_gh_html.py -v
```
