# html-serve integration

The standalone project is maintained in `~/gh/docserve`. Its README.md covers
usage, clickable listing columns, Markdown previews, bundled assets, development,
and verification. Run `html-serve /absolute/path/to/document.md` to view a file.

The dotfiles repository owns these integration points:

- `.chezmoiscripts/run_once_before_install-html-serve.sh` clones a missing
  vimkim/docserve checkout, validates primary main and origin, and runs
  `just sync`. It preserves dirty, unexpected, or linked checkouts.
- `daily-update` refreshes the clean primary checkout and runs `just sync`.
- `~/.config/my-scripts/bin/html-serve` and `serve-html.py` forward to
  `~/.local/bin/html-serve` for existing callers.
- `~/.config/my-scripts/share/serve-html` links to the packaged assets. The
  Markdown skill's Mermaid validator continues to use this compatibility path.

The server, renderer assets, asset builder, tests, and design/research notes have
moved to the standalone repository. The server reads assets from its own Python
package; the compatibility link does not control server rendering.

## Migration and deployment

After approved merges, run the bootstrap script from the configured source
checkout before `chezmoi-apply-unmodified`. The helper excludes run scripts.
The bootstrap installs from primary main. When an old asset directory exists,
run the bootstrap directly: a parent `chezmoi apply` holds the state lock and
cannot perform this transition. The script stops with a migration hint in that
case, preserving the old directory. Before the old asset directory is
replaced with a link, the bootstrap compares every file with the extracted
package assets and backs up an exact match to
`~/.local/state/html-serve/legacy-assets`. It then clears only that directory's
previous chezmoi state record so the helper can create the new symlink. A locally changed asset directory or
an occupied backup path is preserved and reported; report the helper's skip
and remaining difference too. A directory symlink is also preserved for review
if it points somewhere else. Re-running the bootstrap is safe.

Review and verify these absolute targets with chezmoi diff:

- `/home/vimkim/.config/my-scripts/bin/html-serve`
- `/home/vimkim/.config/my-scripts/bin/serve-html.py`
- `/home/vimkim/.config/my-scripts/bin/daily-update`
- `/home/vimkim/.config/my-scripts/share/serve-html`

`bash -n` and `shellcheck` validate the bootstrap and wrappers. Run
`python3 -B -m unittest discover -s tests -p 'test_html_serve_migration.py' -v`
and the daily-update suite. The migration tests use disposable homes and
stubbed tools; they do not install a global command.

The local migration does not publish a GitHub repository. Fresh-machine cloning
requires the published vimkim/docserve repository. Repository creation and push
remain separate user actions.
