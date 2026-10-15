# html-serve listing and theme research

Research date: 2026-10-15. Repository baseline: `68c90f54e2770a692a450737fdf842c982453654`.
This is research for the companion design, not an implemented behavior change.

The existing Python server and bundled browser renderer can meet the request.
The significant constraints are obtaining real creation timestamps on Linux,
making explicit themes override the operating-system preference throughout the
viewer, and keeping directory sorting deterministic.

## Existing implementation

The [server](../private_dot_config/my-scripts/bin/executable_serve-html.py)
subclasses `SimpleHTTPRequestHandler`. Its `send_head()` explicitly sends every
directory request to `list_directory()`, bypassing index pages, but does not
override the listing method. Inspection of the installed Python implementation
showed a filename-only list ordered with `name.lower()`; there is no creation
metadata layer. The standard handler's GET/HEAD flow and URL translation can
continue to own the HTTP lifecycle. Python documents the handler and its
directory listing extension point in its [3.14 HTTP server reference](https://docs.python.org/3.14/library/http.server.html#http.server.SimpleHTTPRequestHandler).

The [viewer HTML](../private_dot_config/my-scripts/share/serve-html/viewer.html)
declares `color-scheme: light dark`. Both
[viewer CSS](../private_dot_config/my-scripts/share/serve-html/viewer.css) and the
bundled GitHub Markdown CSS use `prefers-color-scheme`. The
[viewer script](../private_dot_config/my-scripts/share/serve-html/viewer.js)
also reads that media query to initialize Mermaid. The current behavior is
therefore automatic selection from the browser preference; dark is not a fixed
application default. The user's requested default should supersede all three
of these selections, together with the root color-scheme declaration.

The [asset package](../tools/serve-html-assets/package.json) pins
`github-markdown-css` 5.9.0, Mermaid 12.2.0, and esbuild 0.28.2. The
[build script](../tools/serve-html-assets/build.mjs) already generates committed
browser assets and their manifest, so adding build-time CSS processing requires
no runtime Node installation.

## Creation and modification timestamps

### Evidence

Python defines `st_mtime` as content modification time and `st_ctime` as metadata
change time. `st_birthtime` is optional and can raise `AttributeError`.
Nanosecond integer attributes avoid floating-point timestamp rounding where
available. These definitions are explicit in the
[Python 3.14 `os.stat_result` reference](https://docs.python.org/3.14/library/os.html#os.stat_result).
CPython 3.14's [POSIX implementation](https://github.com/python/cpython/blob/v3.14.0/Modules/posixmodule.c#L2209)
only exposes birth time when the platform's stat structure supports it or on
Windows; calling Python's ordinary `stat()` is not a general Linux birth-time
solution.

Linux exposes creation time through `statx().stx_btime`. The interface appeared
in Linux 4.11 and glibc 2.28. Callers request `STATX_BTIME` and must check the
returned `stx_mask`: a successful syscall does not guarantee the requested
field was supplied. `AT_SYMLINK_NOFOLLOW` changes the request from target
metadata to the link's own metadata. These contracts come from
[Linux man-pages 6.19, `statx(2)`](https://man7.org/linux/man-pages/man2/statx.2.html).
The kernel's [ext4 inode documentation](https://docs.kernel.org/filesystems/ext4/inodes.html)
also records an inode creation-time field; support must still be checked for
the actual mounted filesystem and file.

Linux distinguishes birth time from ctime. A directory's mtime changes when
direct entries are created or deleted; it does not mean the newest modification
anywhere under that directory. File mtime can also be explicitly set, so it
is useful filesystem metadata rather than an edit-history audit. These
semantics are described in [Linux `inode(7)`](https://man7.org/linux/man-pages/man7/inode.7.html).

GNU `stat` exposes `%w` as formatted birth time, using `-` when unavailable,
and `%W` as epoch seconds, using zero when unavailable. `--printf` interprets
backslash escapes and supports custom record framing. See the
[GNU Coreutils stat manual](https://www.gnu.org/software/coreutils/manual/html_node/stat-invocation.html).
GNU Coreutils [8.32 source](https://github.com/coreutils/coreutils/blob/v8.32/src/stat.c)
confirms that `%w`/`%W` request `STATX_BTIME`, `%n` emits the operand without
quoting, `-L` follows links, and a missing file does not prevent later operands
from producing records. Two traps are visible there: an operand equal to `-`
means standard input even after `--`, and `%W` clamps negative timestamps to
zero. A numeric zero alone cannot prove that creation time is unknown.

### Implementation choice

Recommendation: isolate metadata collection behind one small Python interface.
Read ordinary stat metadata once per entry, take native `st_birthtime_ns` or
`st_birthtime` when exposed, and otherwise obtain birth times in bounded GNU
`stat` batches on Linux. Return an explicit missing value when a field cannot
be obtained. Never substitute ctime, mtime, the request time, or an epoch date
for creation time.

| Option | Benefit | Cost and conclusion |
| --- | --- | --- |
| Python stat only | Smallest implementation; no subprocess | Real creation time is missing on the inspected Linux Python runtime. Insufficient alone. |
| GNU stat batches | Installed locally; command owns Linux ABI; Python packages unnecessary | Optional system utility and bounded subprocess management. Recommended here. |
| `ctypes` calling libc `statx` | No subprocess; direct per-entry syscall | Must own structure layout, function signatures, symbol availability, errno, platform guards, and fallback behavior. Defer unless measured batch cost justifies it. |

Python's [ctypes documentation](https://docs.python.org/3.14/library/ctypes.html)
describes explicit foreign structure layouts, function prototypes, library
loading, and errno handling. The assessment that this maintenance cost exceeds
the needs of a small listing server is a design judgment, not a claim that
ctypes cannot implement statx.

For the chosen target-metadata policy, use `-L` consistently with Python's
following stat. Keep the link's visible filename and link marker. A dangling
link remains listed with unknown target timestamps; do not silently change to
its own inode timestamps. The existing server follows links when serving, so
this policy makes the displayed dates describe what a click opens.

A candidate process boundary is an argv sequence, without a shell:

```python
[
    stat_executable,
    "-L",
    "--printf=%n\\0%w\\0",
    "--",
    *["./" + name for name in batch],
]
```

Set the child's `cwd` to the listed directory, capture bytes, and use a fixed
locale and UTC timezone. Prefixing every operand with `./` also handles a file
literally named `-`. Match returned operand bytes to the requested operands;
do not pair records with inputs by position, since failed operands emit no
record. NUL framing preserves filenames containing spaces, tabs, quotes,
newlines, and undecodable filesystem bytes. Use `%w == '-'` as the availability
test; parse known UTC dates for display. Preserve original precision until the
presentation boundary. `%.9W` is an optional numeric convenience only if the
negative-time caveat is handled.

Use bounded batches by encoded argument size and entry count, a total lookup
deadline, and an `E2BIG` split fallback. Linux limits the combined argument and
environment size; fixed entry count alone is insufficient for arbitrary name
lengths. See [`execve(2)` argument-size limits](https://man7.org/linux/man-pages/man2/execve.2.html).
Catch missing utility, timeout, malformed output, missing operands, and ordinary
nonzero exit status. Retain complete valid records where safe and leave the
remainder unknown. A listing should still load when optional birth-time lookup
fails. Directory enumeration and subsequent metadata calls are not an atomic
snapshot; tolerate removal/replacement races.

### Local observations

Read-only runtime inspection found Python 3.14.6 without `st_birthtime`, Linux
5.14, glibc 2.34, and GNU Coreutils `stat` 8.32. GNU stat returned real creation
timestamps for files on the working filesystem. A temporary-directory probe
verified NUL framing for leading-hyphen, newline, and quote filenames. Including
a nonexistent operand returned status 1 while retaining the successful records.
The probe removed its temporary files. These observations demonstrate local
feasibility; they do not establish support for every filesystem or platform.

## Directory ordering and controls

Sorting must be a specified product rule. Alphabetical order, natural numeric
order, and locale collation are different operations. For example,
`chapter-10.md` precedes `chapter-2.md` lexically, while natural numeric order
reverses them. Locale collation adds language-dependent treatment of case and
accents; ECMAScript's [Internationalization specification](https://tc39.es/ecma402/#sec-intl.collator.prototype.compare)
defines locale and numeric collation options and allows implementation-specific
collation details.

The user confirmed that title means the displayed filename. For this request,
do not open every HTML/Markdown document to discover embedded titles. Offer
`Modified: newest first` as the default and `Title: A–Z` as the alternative.
For names use `(name.casefold(), name)`; for equal mtimes use the same name key.
Python documents the Unicode caseless comparison intent of
[`str.casefold()`](https://docs.python.org/3.14/library/stdtypes.html#str.casefold).
This is deterministic filename ordering, not a promise of locale-specific
dictionary order. Interleave directories and files by the chosen key so the
default remains globally newest first. Pin parent navigation outside the sorted
entries and place unknown mtimes last.

Server-rendered sort links or a GET form make the sort choice bookmarkable and
usable before JavaScript loads. Use a semantic table with `Title`, `Created`,
and `Modified` columns. Set `aria-sort` only on the active sorted header and
make the active sort visible in text. W3C's
[table guidance](https://www.w3.org/WAI/ARIA/apg/patterns/table/) and
[sortable table example](https://www.w3.org/WAI/ARIA/apg/patterns/table/examples/sortable-table/)
support native table semantics and an active-header sort indication. Their
button example is for in-place sorting; URL navigation can retain ordinary
link semantics. Do not make the entire table an ARIA grid.

## Light default and explicit dark toggle

### CSS evidence and recommendation

The pinned [github-markdown-css 5.9.0 README](https://github.com/sindresorhus/github-markdown-css/blob/v5.9.0/readme.md)
provides an automatic stylesheet and separate light-only/dark-only files.
Inspection of the currently bundled automatic stylesheet found both
`.markdown-body` and `[data-theme=...]` selectors inside the system-preference
media rules. A root attribute alone therefore cannot force the opposite theme.

The pinned [light-only source](https://github.com/sindresorhus/github-markdown-css/blob/v5.9.0/github-markdown-light.css)
and [dark-only source](https://github.com/sindresorhus/github-markdown-css/blob/v5.9.0/github-markdown-dark.css)
have `.markdown-body` selector families and no media, font-face, keyframe, or
root declarations. They are suitable inputs for build-time selector scoping.
Both retain some custom-property references, including keyboard-focus and
border colors, so the shared theme CSS must supply those values and verify
focus visibility.

Recommendation: wrap each fixed stylesheet in its corresponding
`:root[data-theme="light"]` or `:root[data-theme="dark"]` nesting rule, then
lower CSS nesting with the existing esbuild dependency into one committed
stylesheet. esbuild documents its [CSS loader and syntax transforms](https://esbuild.github.io/content-types/#css)
and the [`nesting` compatibility setting](https://esbuild.github.io/api/#supported).
Use explicit browser targets, such as Chrome 109, Firefox 115, and Safari 16,
and force `supported: { nesting: false }` so the committed output uses flattened
selectors. A temporary feasibility probe with esbuild 0.28.2 processed both
pinned 22,219-byte stylesheets into 57,995 bytes, with the expected scoped
selectors, zero OS-preference rules, and no compiler warnings. It removed its
temporary files. This verifies compilation feasibility, not browser rendering.
The combined stylesheet avoids adding a runtime stylesheet download whenever
the user toggles.

### Preference ownership and persistence

The HTML root should begin with `data-theme="light"`. A small synchronous
classic script in the head, before themed content, may replace it with a valid
stored `dark` or `light` preference. Do not defer this first selection until
the Markdown module or document fetch completes. Classic parser-inserted
scripts and deferred/module execution differ as specified by the
[HTML script processing model](https://html.spec.whatwg.org/multipage/scripting.html#the-script-element).
Selecting the attribute before themed content can paint is a design inference
from that model; verify it under slow headless-browser loading.

Use the same explicit root state for viewer backgrounds, controls, GitHub
Markdown rules, and Mermaid. Set the root `color-scheme` to the selected
scheme so browser controls match; that property describes supported color
schemes and does not itself rewrite arbitrary author colors. See
[CSS Color Adjustment Level 1](https://www.w3.org/TR/css-color-adjust-1/#color-scheme-prop).

Persist a namespaced preference in localStorage, catching errors around both
reads and writes. Storage getters can fail by policy and writes can fail;
the toggle must still work for the current page. These are specified in the
[HTML Web Storage standard](https://html.spec.whatwg.org/multipage/webstorage.html#the-localstorage-attribute).
The [origin definition](https://html.spec.whatwg.org/multipage/browsers.html#concept-origin)
includes scheme, host, and port. Consequently, the existing command's alternate
LAN/VPN addresses and dynamically selected ports can have separate saved
preferences. Persistence across every invocation or address is not guaranteed.

### Mermaid must participate

Mermaid's [theme documentation](https://mermaid.js.org/config/theming.html)
supports explicit theme configuration and allows author frontmatter/directives
to override page defaults. Its [render API](https://mermaid.js.org/config/usage.html#api-usage)
returns SVG for a source string. Existing generated SVG is a render result;
changing the page's root theme does not regenerate its theme-specific colors.

Recommendation: retain each diagram's source and target element. On a theme
change, render only those diagrams with the new theme, leaving Markdown and
KaTeX content in place. Serialize Mermaid initialization and render calls,
coalesce rapid toggles to the newest requested theme, and reject stale output
before committing it. A stale-result check alone is insufficient if concurrent
operations can mutate Mermaid's shared configuration. Keep errors local to
each diagram. Preserve author-specified diagram styling and do not promise
automatic recoloring of arbitrary embedded SVG/image files.

## Verification implications

Implementation should cover missing birth-time support, partial stat failure,
names containing delimiters, a literal `-` filename, target-following links and
dangling links, equal and unknown mtimes, directory navigation, and GET/HEAD
parity. Test light first visit even with a dark browser preference, both toggle
directions, stored preference restoration, denied storage, and toggling while
Mermaid is still rendering. Browser checks should include keyboard focus,
mobile tables, contrast, and pre-paint theme selection. The existing Python
and headless-browser test suites already provide appropriate verification seams;
no framework migration is needed.
