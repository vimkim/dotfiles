# Serve HTML from an SSH terminal

Run `html-serve` in an SSH terminal from the directory you want to serve:

```sh
html-serve
html-serve --file review.html
html-serve --port 8080
html-serve --directory '/another/output directory'
```

The wrapper is on PATH in Bash, Zsh, and Nushell. It supplies `--directory .`
and forwards all options to `serve-html.py`; an explicit `--directory` overrides
the current directory. With no `--file`, printed links point to `/`, which
serves `index.html` or `index.htm` when present and a directory listing otherwise.

The `serve-html` agent skill can also suggest a command after creating an HTML
file. Run that command yourself in an SSH terminal:

```bash
PYTHONDONTWRITEBYTECODE=1 python "$HOME/.config/my-scripts/bin/serve-html.py" --bind 0.0.0.0 --directory '/absolute/path/to/output' --file 'review.html'
```

The CLI starts a foreground HTTP server, chooses a memorable free port, and
prints plain URLs for the server's active Tailscale/VPN and LAN IPv4
addresses. Open a printed URL from your PC, then press Ctrl+C in the SSH terminal
to stop the server. The port stays bound throughout serving; concurrent runs get
different ports. The directory includes adjacent CSS, JavaScript, and images.

Each address appears once as a plain URL, followed by a short network label
such as Tailscale or LAN. The output needs no Markdown renderer, and terminals
that recognize URLs can make them clickable.

HTTP access logs, such as GET and HEAD requests, are quiet by default. Startup
links and errors remain visible. Add `--verbose` to print request logs.

With no `--port`, or with `--port 0`, the CLI tries these patterns in order:

| Priority | Pattern | Examples |
| --- | --- | --- |
| 1 | Four identical digits | `7777`, `8888`, `9999`, `5555`, `4444`, `3333`, `2222`, `1111` (in this order) |
| 2 | Adjacent repeated pairs | `1122`, `2233`, `3322`, `7788` |
| 3 | Three repeats next to an adjacent digit | `1112`, `2223`, `2333`, `7778` |
| 4 | Ascending or descending sequences | `1234`, `5678`, `8765`, `9876` |
| 5 | Other repeated pairs | `2255`, `5577`, `8800` |
| 6 | Alternating pairs | `1212`, `4545`, `8080`, `9090` |
| 7 | Mirrored pairs | `1221`, `3443`, `8008`, `9009` |
| 8 | Round thousands | `7000`, `8000`, `9000` |
| 9 | Round hundreds | `2500`, `8100` |

Within each pattern after the first, lower port numbers come first. Occupied
or permission-denied ports are skipped. Automatic selection excludes the
four-digit ports in the [Fetch port-blocking list](https://fetch.spec.whatwg.org/#port-blocking),
including `6666`, which browsers block for HTTP. After the memorable patterns,
the CLI tries the remaining allowed ports from `1024` to `9999`, then asks the
kernel for an available port if every four-digit choice is unavailable. Each
attempt binds the actual server and retains the successful socket.

`--file` optionally links directly to an existing `.html` or `.htm` file and can
name a file in a subdirectory. Without it, no HTML file is required.
`--port PORT` with a nonzero value requires that exact port; an occupied port
fails before any links are printed. `--interface NAME` limits the printed links,
while `--bind ADDRESS` controls which IPv4 address accepts connections. A
loopback bind prints only a local link. Python 3 and Linux `ip` (iproute2) are
required for network discovery.
The CLI never opens a browser. Reachability from a PC depends on its network
route to the server.

## Source and installation

The maintained sources are
`private_dot_config/my-scripts/bin/executable_serve-html.py` and
`private_dot_config/my-scripts/bin/executable_html-serve`. Chezmoi installs them
as `~/.config/my-scripts/bin/serve-html.py` and
`~/.config/my-scripts/bin/html-serve` with executable permissions. The
`vimkim/my-skills` collection maintains only the agent instructions.

Review both targets, then deploy with the repository helper after merge approval:

```bash
chezmoi diff -- "$HOME/.config/my-scripts/bin/html-serve"
chezmoi diff -- "$HOME/.config/my-scripts/bin/serve-html.py"
chezmoi-apply-unmodified
```

For a topic worktree, pass `--source /absolute/path/to/task-worktree` before the
subcommand when reviewing the rendered target.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_serve_html.py' -v
```

The tests exercise the CLI's live HTTP lifecycle, preferred port ordering,
occupied preferred ports, automatic fallback and reservation,
concurrent servers, occupied fixed ports, Ctrl+C shutdown, encoded HTML paths,
adjacent assets, and interface discovery. They also verify the wrapper from a
current directory without an index page and its option forwarding. CLI
integration uses temporary files and a deterministic `ip` fixture. No deployed
files or browsers are used.
