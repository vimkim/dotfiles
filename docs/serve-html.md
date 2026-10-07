# Serve HTML from an SSH terminal

The `serve-html` agent skill suggests a command after creating an HTML file.
Run that command yourself in an SSH terminal:

```bash
PYTHONDONTWRITEBYTECODE=1 python "$HOME/.config/my-scripts/bin/serve-html.py" --bind 0.0.0.0 --directory '/absolute/path/to/output' --file 'review.html'
```

The CLI starts a foreground HTTP server, asks the kernel for a free port, and
prints Markdown links for the server's active Tailscale/VPN and LAN IPv4
addresses. Open a printed URL from your PC, then press Ctrl+C in the SSH terminal
to stop the server. The port stays bound throughout serving; concurrent runs get
different ports. The directory includes adjacent CSS, JavaScript, and images.

`--file` defaults to `index.html` and can name an HTML file in a subdirectory.
`--port PORT` requires a particular port; an occupied port fails before any links
are printed. `--interface NAME` limits the printed links, while `--bind ADDRESS`
controls which IPv4 address accepts connections. A loopback bind prints only a
local link. Python 3 and Linux `ip` (iproute2) are required for network discovery.
The CLI never opens a browser. Reachability from a PC depends on its network
route to the server.

## Source and installation

The maintained source is
`private_dot_config/my-scripts/bin/executable_serve-html.py`. Chezmoi installs it
as `~/.config/my-scripts/bin/serve-html.py` with executable permissions. The
`vimkim/my-skills` collection maintains only the agent instructions.

Review and install just this target:

```bash
chezmoi diff -- "$HOME/.config/my-scripts/bin/serve-html.py"
chezmoi apply -- "$HOME/.config/my-scripts/bin/serve-html.py"
```

For a topic worktree, pass `--source /absolute/path/to/task-worktree` before the
subcommand when reviewing the rendered target.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_serve_html.py' -v
```

The tests exercise the CLI's live HTTP lifecycle, automatic reserved ports,
concurrent servers, occupied fixed ports, Ctrl+C shutdown, encoded HTML paths,
adjacent assets, and interface discovery. CLI integration uses temporary files
and a deterministic `ip` fixture. No deployed files or browsers are used.
