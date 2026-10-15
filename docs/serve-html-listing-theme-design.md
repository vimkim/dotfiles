# html-serve directory listing and Markdown theme design

Status: accepted on 2026-10-15; implementation tracked in
[issue #1](https://github.com/vimkim/dotfiles/issues/1).
The original design was based on repository commit `68c90f5`. Supporting primary
sources and experiments are in
[the research note](serve-html-listing-theme-research.md). This is a local
review document; implementation specs and tickets belong in
[`vimkim/dotfiles` GitHub Issues](https://github.com/vimkim/dotfiles/issues).

## Intended behavior

Opening a directory shows **Title**, **Created**, and **Modified** columns.
Entries initially appear by modification time, newest first. **Title A–Z**
switches to alphabetical order. The user confirmed that title means the
filename, including its extension; listing a directory does not read document
contents to discover headings or HTML titles.

Opening Markdown starts in **light mode** when the browser has no saved
html-serve theme choice, including when the operating system prefers dark.
A **Dark mode** toggle switches both ways and remembers the explicit choice.
A saved dark choice takes precedence on later visits to the same origin.

Example directory view; dates here are illustrative:

```text
Directory listing for /reports/
Sort: [Modified · newest first]  [Title · A–Z]
Times: server local

Title                 Created              Modified
../                   —                    —
review.md             2026-10-12 09:00:00  2026-10-15 19:42:00
architecture.html     2026-10-10 14:00:00  2026-10-15 18:30:00
figures/              Unavailable          2026-10-14 12:00:00
```

Files and directories share the selected order; only the synthetic parent
link stays first. There is no parent link at the serving root. Directory dates
refer to the directory itself. Editing an existing child's contents does not
necessarily change its directory's modification time.

## Implementation at design time and constraints

At design time,
[`PreviewHTTPRequestHandler.send_head()`](../private_dot_config/my-scripts/bin/executable_serve-html.py)
already forced directory URLs through `list_directory()`, bypassing implicit
index pages. The inherited Python implementation showed a case-insensitive
filename list without dates. Override that method, keeping the existing
directory routing and HTTP lifecycle.

The original [viewer HTML](../private_dot_config/my-scripts/share/serve-html/viewer.html),
[CSS](../private_dot_config/my-scripts/share/serve-html/viewer.css), and
[JavaScript](../private_dot_config/my-scripts/share/serve-html/viewer.js) each
contribute to automatic dark mode: the page declares both color schemes, CSS
uses operating-system media queries, and Mermaid independently calls
`matchMedia()`. The bundled GitHub Markdown CSS also contains those media
queries. An explicit theme must replace all four automatic choices.

Retain the Python standard-library server and locally bundled browser assets.
Node/npm remain build/test tools. The shell wrapper, CLI arguments, port
selection, printed URLs, raw Markdown, explicit HTML files, and adjacent assets
keep their existing behavior. Theme controls apply to Markdown; the new
directory listing uses a fixed light presentation.

## Directory listing interface

Use ordinary server-rendered links and a semantic table. The whole listing,
including sorting and navigation, works without JavaScript. Two links labeled
**Modified · newest first** and **Title · A–Z** make the available orders
explicit. Mark the active link with `aria-current="true"` and the active table
header with `aria-sort="descending"` or `aria-sort="ascending"`.

| Directory URL | Order |
| --- | --- |
| `/reports/` | Modified, newest first |
| `/reports/?sort=modified` | Modified, newest first |
| `/reports/?sort=title` | Filename, A–Z |
| Missing, unknown, empty, or repeated `sort` values | Default modified order |

Parse with `keep_blank_values=True` and accept exactly one recognized value.
Parent and child directory links retain
the recognized order. File links retain their existing URLs. Browser Back
returns to the sorted directory URL; the Markdown toolbar's existing **Files**
link opens the parent directory in default modified order. There is no saved
sort preference: a bare directory URL always means newest first.

For modified order, sort known `st_mtime_ns` values descending, then break ties
by `(name.casefold(), name)`. Entries with unavailable modification metadata
sort after all known dates. For title order, use `(name.casefold(), name)`.
This is deterministic Unicode ordering, independent of server locale; digits
sort as characters, so `report10.md` precedes `report2.md`.

Render dates to seconds in server local time. Each known date is a `<time>`
element whose `datetime` contains an ISO 8601 timestamp with its offset; its
tooltip also shows that offset. Sorting retains nanosecond precision even
when displayed seconds match. Show **Unavailable** for missing metadata,
with a short explanation beside the table that creation dates depend on the
filesystem. The parent row uses em dashes because it is navigation.

Keep hidden entries, directory slash suffixes, and symlink markers. Follow a
symlink for both displayed dates and modification ordering, matching the file
or directory the user opens; retain the symlink's name and URL. Dangling links
remain visible with unavailable dates. Do not recurse into child directories.

Escape filenames and displayed paths as HTML text, and URL-encode links
separately. Cover spaces, Unicode, quotes, HTML metacharacters, newlines,
leading hyphens, and a filename exactly `-`. A horizontally scrollable table
preserves all columns on narrow screens; long filenames wrap inside their
cell. Keyboard focus must remain visible.

## Metadata implementation

Keep the server-side implementation in `serve-html.py`. A small internal
`directory_entries(path)` interface returns records containing the actual
name, directory/symlink flags, `modified_ns`, and optional timezone-aware
creation timestamp. Collection owns filesystem errors and provider selection;
the renderer receives normalized records. A pure
`render_directory(entries, request_path, sort_mode)` produces UTF-8 bytes.
The handler supplies HTTP headers and returns `io.BytesIO`, preserving GET and
HEAD behavior and accurate `Content-Length`.

Use `os.scandir()` and target-following `DirEntry.stat()` for modification
times and entry type. Read `st_birthtime_ns` or `st_birthtime` if the platform
actually exposes one; valid epoch-zero and negative timestamps remain dates.
For entries whose birth time is absent, use the Linux GNU `stat` executable as
an optional adapter:

```python
subprocess.run(
    ["stat", "--dereference", r"--printf=%n\0%w\0", "--", *operands],
    cwd=directory, env=stat_environment, capture_output=True, timeout=remaining,
)
```

`stat_environment` preserves the environment but sets `LC_ALL=C` and `TZ=UTC0`.
Each operand is `./` plus the actual child filename. The prefix also prevents
GNU `stat` from treating a file named `-` as standard input. Capture bytes,
frame records with NUL, and match each returned operand to the enumerated
filename with `os.fsencode()`; do not pair results by position. GNU `stat`
can return successful rows even when another operand fails.

Treat `%w == '-'` as unavailable. Parse known UTC `%w` values with Python's
datetime facilities; subsecond precision beyond microseconds may be discarded
for creation-date display. Reject malformed or out-of-range values as
unavailable. Do not use `%W == 0` to infer availability: GNU `stat` also uses
zero for an unknown birth time. Never substitute `st_ctime`, access time,
Git history, or modification time for creation time. Birth time describes the
current filesystem object; copies and Git checkouts can create a new object.

Bound batches to 128 operands and 32 KiB of encoded argument bytes. On
`E2BIG`, split the batch while budget remains. Use a two-second total
wall-clock budget for all birth-time subprocess lookups in one listing;
preserve results already obtained and mark unresolved creation dates
unavailable. A missing/incompatible `stat`, timeout, unsupported filesystem,
or disappearing entry must leave the rest of the listing usable. Emit lookup
diagnostics only with the existing `--verbose` option. Native directory
enumeration/stat calls can still block on a slow filesystem; the subprocess
budget is not a total request timeout.

The implementation is O(n log n) for ordering, with O(n) metadata reads and
bounded subprocess batches. Do not cache dates across requests: refreshing
the listing should reflect edits. Metadata is a best-effort observation,
not an atomic filesystem snapshot.

## Theme module and rendering

Add a small classic `theme.js`, loaded synchronously in the viewer `<head>`
before stylesheets. The HTML starts with `<html data-theme="light">` and
`<meta name="color-scheme" content="light">`. Bootstrap reads
`localStorage["serve-html.theme.v1"]`; only `light` and `dark` are valid.
Storage access is guarded by `try/catch`. An absent, invalid, or unreadable
value selects light. Set the root attribute and color-scheme metadata before
content can paint. If the script fails, the HTML and CSS still default light.

The theme module owns preference loading, the toolbar toggle, persistence,
and one `serve-html-themechange` event on the document. Its interface to the
renderer is the root's `data-theme` plus that event. Use a native
`<button type="button" aria-pressed="false">Dark mode</button>`; pressed means
dark is selected. Keep its accessible name stable. Bind it without depending
on a successful Markdown fetch or diagram render. Hide it until initialized
so a failed script does not leave a nonfunctional control. Storage write
failures leave the current page's toggle fully usable.

The preference applies to the browser origin, which includes the port.
Switching between LAN and Tailscale URLs or starting the server on a different
port can therefore start light again. No cookie, server configuration, or
cross-origin synchronization is needed. Once chosen, the theme does not track
later operating-system preference changes.

Change the [asset build](../tools/serve-html-assets/build.mjs) to generate
`vendor/github-markdown.css` from the pinned package's fixed
`github-markdown-light.css` and `github-markdown-dark.css`. Wrap each complete
variant in its corresponding `:where(:root[data-theme="light|dark"])` nesting rule
(zero added specificity preserves viewer layout overrides),
then lower nesting using the existing esbuild CSS loader with
`supported: { nesting: false }` and browser targets such as Chrome 109,
Firefox 115, and Safari 16. Both palettes then ship in one render-blocking
stylesheet, and switching requires no stylesheet download. This uses
[esbuild's documented CSS transformation](https://esbuild.github.io/content-types/#css)
and the upstream package's
[fixed theme variants](https://github.com/sindresorhus/github-markdown-css/tree/v5.9.0).

Replace `prefers-color-scheme` rules in `viewer.css` with root-attribute
selectors. Supply explicit page text/background, link, border, muted, focus,
and control colors for both modes, including missing upstream focus and
keyboard-key variables. Set `color-scheme: light` or `dark` consistently.
Retain third-party notices and regenerate the vendor hash manifest. The
existing automatic-theme vendor CSS must no longer be loaded.

Mermaid must read the selected theme instead of `matchMedia()`: light maps to
`default`, dark to `dark`. Retain diagram source strings and stable containers
after initial Markdown parsing. On a theme event, rerender just the diagrams;
do not refetch Markdown, recreate headings, or rerender KaTeX. Preserve scroll
position and focus. Explicit colors authored in images or diagram source
remain author-controlled.

Serialize Mermaid initialization and rendering in one queue because the
Mermaid configuration is shared. Coalesce repeated requests to the latest
theme and use a generation number to discard obsolete SVG results before
installation. A generation check alone does not make concurrent
reinitialization safe. Theme changes during initial import/render enter the
same queue. A malformed diagram remains an individual error; it must not
disable theme switching or hide other content. Keep strict Mermaid security,
Markdown sanitization, and KaTeX's untrusted mode.

## Change map and verification

These are the implementation source-to-deployment mappings. The original
design task changed only this document and its research companion.

| Maintained source | Deployed target or role |
| --- | --- |
| `private_dot_config/my-scripts/bin/executable_serve-html.py` | `/home/vimkim/.config/my-scripts/bin/serve-html.py` |
| `private_dot_config/my-scripts/share/serve-html/viewer.{html,css,js}` | `/home/vimkim/.config/my-scripts/share/serve-html/viewer.{html,css,js}` |
| New `private_dot_config/my-scripts/share/serve-html/theme.js` | `/home/vimkim/.config/my-scripts/share/serve-html/theme.js` |
| Generated `private_dot_config/my-scripts/share/serve-html/vendor/` | `/home/vimkim/.config/my-scripts/share/serve-html/vendor/` |
| `tools/serve-html-assets/build.mjs` | Build only, ignored by chezmoi |
| `tests/test_serve_html.py`, `tests/test_serve_html_browser.mjs` | Verification only, ignored by chezmoi |
| `docs/serve-html.md` and these design/research notes | Repository documentation, ignored by chezmoi |

The inspected server, wrapper, and `viewer.*` sources matched their deployed
targets byte-for-byte; the corresponding task-source `chezmoi diff` was
empty. No deployed file was edited. The wrapper is inspected context, not a
planned implementation change.

Implementation acceptance checks:

| Area | Evidence required |
| --- | --- |
| Default listing | Temporary entries with controlled `os.utime(ns=...)` values appear newest first, with deterministic ties and unknown values last; all three columns appear |
| Alphabetical mode | `?sort=title` sorts mixed-case filenames by the documented key; invalid/repeated values default; directory navigation and redirects preserve recognized sorting |
| Metadata truth | Fixtures exercise real/absent/epoch-zero creation dates, missing utility, timeout, partial GNU output, batching, and `E2BIG`; no ctime fallback |
| Filesystem edge cases | Directories, symlinks, dangling links, vanished entries, special filenames including `-`, and escaped links render and navigate correctly |
| Existing HTTP behavior | GET/HEAD agree; index files remain explicit; raw Markdown, reserved asset paths, encoded URLs, HTML bytes, and adjacent assets retain coverage |
| Initial light mode | Fresh storage with a dark OS preference paints a light page, Markdown body, and Mermaid diagrams; delayed Markdown fetching does not alter the initial theme |
| Toggle and persistence | Keyboard and pointer toggles update page, Markdown, controls, and diagrams; same-origin navigation/reload retains choice; invalid or denied storage falls back safely |
| Rendering races | Rapid toggles during a delayed Mermaid import/render end in the final selected theme; invalid diagrams do not affect other blocks; plain Markdown never loads Mermaid/KaTeX |
| Layout | Both themes retain visible focus, readable tables/code/math, and usable toolbar controls at desktop and 390px width |
| Bundled assets | Rebuild updates CSS/manifest/notices; browser tests block external requests and verify both themes from local assets |

Use the existing Python HTTP suite and headless Playwright suite when
implementing. Extend the current dark/mobile test: it currently expects the
dark operating-system preference to choose dark automatically, which this
design intentionally replaces.

## Implementation sequence and design verification

1. Implement metadata collection and the server-rendered sortable listing;
   verify through live HTTP and focused metadata-provider tests.
2. Add the theme module, scoped CSS build, and toolbar control; verify initial
   light rendering, toggle behavior, storage failure, and persistence.
3. Add serialized Mermaid rerendering and race coverage, then update usage
   documentation and run both existing suites.
4. Commit implementation changes, obtain local merge approval, deploy with
   `chezmoi-apply-unmodified` under repository policy, verify each affected
   target, and clean up the task branch/worktree. A push remains a separate
   request.

Design feasibility evidence: this Linux host exposes birth dates through GNU
`stat` but not Python 3.14.6 `Path.stat()`. A temporary compile probe with the
pinned GitHub CSS 5.9.0 variants and esbuild 0.28.2 produced both explicit
theme scopes with no operating-system preference rules and no compiler
warnings. These establish feasibility; implementation HTTP/browser acceptance
checks above define the implementation verification requirements.
