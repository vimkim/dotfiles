# Serve HTML and Markdown from an SSH terminal

Run `html-serve` in an SSH terminal from the directory you want to serve:

```sh
html-serve
html-serve .
html-serve '/another/output directory'
html-serve path/to/review.html
html-serve README.md
html-serve -d '/another/output directory' -f review.html
html-serve --port 8080
```

The wrapper is on PATH in Bash, Zsh, and Nushell and forwards arguments to
`serve-html.py`. Both commands accept the same paths and options. Directory
URLs always show a listing, even when `index.html` or `index.htm` exists. Click
the filename to open that page, or select it explicitly on the command line.

## Directory listing

Listings show **Title**, **Created**, and **Modified** columns. The default
order is newest modification first. Select **Title · A–Z** to sort by filename,
including its extension. Names use Unicode case-insensitive character order,
with case-sensitive ties; digits sort as characters (`report10` before
`report2`). Files and directories share the order, with `../` first when
inside the serving root.

Sorting works without JavaScript and is recorded in the directory URL:
`?sort=title` selects alphabetical order and `?sort=modified` selects newest
first. Parent and child directory links retain the selected order. A bare
directory URL always starts newest first. File links retain their normal URLs;
browser Back returns to the sorted listing, while the Markdown **Files** link
opens its parent listing in default order.

Dates use the server's local timezone; hover over a date for its ISO timestamp
and UTC offset. Directory dates describe the directory itself, not its newest
descendant. Symlink dates follow the target while the visible name retains `@`;
dangling links remain listed with unavailable dates.

**Created** means the filesystem object's birth date, which can change when
files are copied or checked out. It is **Unavailable** when the filesystem
does not supply it. On Linux, optional GNU Coreutils `stat` supplies birth dates
in bounded batches; missing tools, unsupported filesystems, or lookup timeouts
leave the listing usable. Metadata-change time is never substituted for birth
time. Add `--verbose` to see lookup diagnostics.

## Paths and file selection

| Arguments | Serving directory | Printed links |
| --- | --- | --- |
| None | Current directory | Directory listing at `/` |
| `DIR` (including `.`) | Directory's Git repository root, or `DIR` outside Git | Root listing and the selected directory listing |
| `PATH/FILE` | File's Git repository root, or parent directory outside Git | Root listing and the selected file |
| `-d DIR` or `--directory DIR` | `DIR` | Directory listing at `/` |
| `-f FILE` or `--file FILE` | Current directory | Root listing and `FILE` relative to the current directory |
| `DIR -f FILE` | `DIR` | Root listing and `FILE` relative to `DIR` |
| `-d DIR -f FILE` | `DIR` | Root listing and `FILE` relative to `DIR` |

A positional path can be relative or absolute; quoted `~` paths are expanded.
It must name an existing directory or regular file. Any regular file can be
selected: HTML opens as a page, Markdown uses the preview, and other formats
use the browser's normal behavior. Selecting a positional directory or file
serves its enclosing Git repository root, so links and assets elsewhere in the
repository remain accessible. Detection starts from the selected directory or
the file's directory, regardless of your current directory. Nested repositories
and linked worktrees use their own roots.
Outside a repository, or if Git is unavailable or detection fails, the selected
directory or the file's parent directory is served instead. With no path argument,
the current directory is served without Git discovery.

`--directory` (`-d`) requires a directory. `--file` (`-f`) requires a file path
relative to the selected serving directory; absolute paths and `..` components
are rejected. Use a positional file path to select a file outside the current
directory, or choose its serving root explicitly with `-d`.

A positional path together with `-d` is an error. A positional file together
with `-f` is also an error. A positional directory can be combined with `-f`.
For example, from a repository root, `html-serve docs -f nested/review.html`
serves `docs` and prints a link to `/nested/review.html`;
`html-serve docs/nested/review.html` serves the repository root and prints a
link to `/docs/nested/review.html` alongside the root listing link.
`html-serve docs/nested` serves the repository root and also prints a link to
`/docs/nested/`. Outside Git, selecting the file serves `docs/nested` and links to
`/review.html` alongside `/`. To explicitly serve only the file's parent
directory, use `html-serve docs/nested -f review.html`.

## Markdown preview

Click any `.md` or `.markdown` file in the directory listing to read it as a
rendered page. Direct links and links from other documents also render by
default, including uppercase extensions. A URL such as `/docs/design.md` stays
at that address; no preview option or generated `.html` file is needed.
`html-serve --file README.md` prints links directly to the preview.

The viewer supports GitHub Flavored Markdown tables, task lists, strikethrough,
heading anchors, and these document features:

````markdown
```mermaid
flowchart LR
    Markdown --> Preview
```

![Architecture](./figures/architecture.svg)
![Remote SVG](https://example.com/architecture.svg)

Inline math: $E = mc^2$

$$
\int_0^1 x^2\,dx = \frac{1}{3}
$$
````

Relative image and document links resolve from the Markdown file's original
directory. Keep referenced files within the directory being served. SVGs are
displayed as images. LaTeX equations use KaTeX's supported math syntax; ordinary
code blocks and inline code remain literal. Invalid diagrams or equations show
their source and error while the remaining document stays readable.

The toolbar has **Files** and **Raw** links. Add `?raw=1` to a Markdown URL to
read the original source as UTF-8 plain text. Preview requires JavaScript in a
modern browser. It starts in **light mode**, including when the operating
system prefers dark. Use the toolbar's **Dark mode** toggle to switch either
way; the chosen theme also updates Mermaid diagrams. The browser remembers the
choice for the same scheme, host, and port. A different LAN/VPN address or port
can start light again. If browser storage is unavailable, the toggle still
works for the current page. Explicit colors inside images and diagram source
remain controlled by their authors. Document HTML
is sanitized; Mermaid uses its strict security setting and KaTeX disables
trusted commands.

Renderer scripts, styles, diagram modules, and math fonts are bundled locally.
No GitHub request, CDN, Node, npm, or Python package installation is needed to
serve documents. Remote images still require access to their host. Markdown
rendering happens in the browser; HTTP clients receive the viewer HTML at the
default URL and can request `?raw=1` for the document source. The internal URL
prefix `/__serve_html__/` is reserved for viewer assets.

## Server options

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

The **Root directory** section prints a plain root URL for each address, followed
by a short network label such as Tailscale or LAN. When a selected directory or
file has a different URL, **Selected path** prints its direct URL for every
address too. Directory links end in `/`; spaces, Unicode, and special characters
are URL-encoded. A selection that is already the root uses the root URLs without
duplicates. The output needs no Markdown renderer, and terminals that recognize
URLs can make them clickable.

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
`~/.config/my-scripts/bin/html-serve` with executable permissions. The viewer
and its bundled dependencies are maintained in
`private_dot_config/my-scripts/share/serve-html/` and installed under
`~/.config/my-scripts/share/serve-html/`. Keep that directory alongside the
scripts when copying the installation. The
`vimkim/my-skills` collection maintains only the agent instructions.

Review the scripts and asset directory, then deploy with the repository helper
after merge approval:

```bash
chezmoi diff -- "$HOME/.config/my-scripts/bin/html-serve"
chezmoi diff -- "$HOME/.config/my-scripts/bin/serve-html.py"
chezmoi diff -- "$HOME/.config/my-scripts/share/serve-html"
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
adjacent assets, and interface discovery. They also verify directory listings
with index pages present, explicit index links, directory redirects, positional
directories and files, root and direct links on each network, Git root discovery
for nested repositories and linked worktrees, parent-directory fallback,
explicit directory overrides, short and
long options, and conflicting arguments. CLI integration uses temporary files
and a deterministic `ip` fixture. No deployed
files are used. They also cover Markdown routing, raw responses, GET/HEAD,
SVG content types, asset paths, and rendering with `--verbose`. Listing checks
cover nanosecond modification ordering, alphabetical mode and navigation,
special filenames, symlink dates, birth-date availability, partial lookup
results, batching, argument-size fallback, and lookup deadlines.

Headless Chromium verification exercises actual clicks from the directory
listing, direct encoded URLs, relative Markdown links and SVG images, a remote
SVG image from a second local HTTP origin, Mermaid, LaTeX math, heading IDs,
sanitization, errors within individual blocks, light and dark mobile layouts,
saved themes, denied storage, early theme selection during slow loading,
rapid toggles during Mermaid loading, directory sorting without JavaScript,
and existing HTML behavior. Network requests outside localhost are blocked in
the main rendering scenario, and a plain document verifies lazy loading:

```sh
npm --prefix tools/serve-html-assets ci
# Install a headless test browser if it is not cached already.
cd tools/serve-html-assets
npx playwright install chromium --only-shell
npm test
```

Set `SERVE_HTML_CHROMIUM_EXECUTABLE` to use an existing Chromium binary.
Set `SERVE_HTML_SCREENSHOT` to an absolute PNG path to capture the rendered
fixture. All browser launches in the test are headless.

## Updating bundled assets

The build dependencies are pinned in `tools/serve-html-assets/package-lock.json`.
Node 22.12 or later and npm are needed only to rebuild the committed assets or
run browser tests:

```sh
npm --prefix tools/serve-html-assets ci
npm --prefix tools/serve-html-assets run build
```

The build creates the `vendor/` directory, includes third-party license texts,
and records package versions and file SHA-256 hashes in `vendor/manifest.json`.
Commit the regenerated files together with dependency changes. The source
viewer HTML, CSS, and JavaScript live outside `vendor/` and can be edited
directly. `theme.js` applies the saved preference before stylesheets load.
The build scopes the pinned light-only and dark-only GitHub Markdown styles
into one stylesheet so theme changes need no additional download. Build tools
and test dependencies are excluded from chezmoi deployment.
