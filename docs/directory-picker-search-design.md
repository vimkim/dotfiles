# Directory picker search and metadata design

Status: accepted on 2026-10-07 after confirmation of shared understanding and
documentation review. This document records confirmed
requirements, source evidence, and a proposed refactoring plan. Runtime
behavior has not changed. The existing behavior remains documented in
[directory-picker.md](directory-picker.md).

## Confirmed requirements

- Bare Nushell `c` opens an interactive list of directories.
- With an empty query, child directories appear in recency order, newest first.
- Directory picker recency means the directory's own modification time, not
  creation time or the newest modification among its descendants. Adding,
  deleting, or renaming direct entries can change it; editing the contents of an
  existing file may not.
- A nonempty query uses fzf's fuzzy matching and ranks candidates by matching
  score. Consecutive substring matching is not required.
- Only the directory's own name participates in matching. Displayed metadata
  and ancestor path fragments do not.
- Metadata is visible while choosing a directory, with a presentation similar
  to the file picker: directory entry size, modification date/time, icons,
  directory name, and symlink information. Entry size does not mean total
  contents size. eza normally displays `-` for directory size; showing the
  entry's byte count is the stated presentation assumption for this design.
- Keep `c PATH` as direct navigation. Add `c --query TEXT` for opening the
  picker with initial query text.
- Keep `../` as the first candidate with an empty query. Ordinary name
  searches filter it out.
- A directory symlink uses the target directory's modification time for both
  recency and the displayed Modified value. Navigation still uses the symlink
  path rather than resolving it to the target path.
- Retain normal fzf extended query syntax and smart-case matching. Multiple
  terms, prefix/suffix matching, quoted terms, and negation remain available,
  all restricted to the name field. A spaces-only query behaves as empty.
- Python renders similar metadata columns; eza is not a new dependency.
- `c PATH --query TEXT` opens the picker inside PATH with that initial query.
  Without PATH, an explicit query option browses the current directory.

## Intended command behavior

| Command | Result |
| --- | --- |
| `c` | Browse the current directory with an empty query |
| `c PATH` | Navigate directly to PATH, as before |
| `c --query TEXT` | Browse the current directory with initial query TEXT |
| `c PATH --query TEXT` | Browse PATH with initial query TEXT |
| `c --query ""` | Explicitly open the picker with an empty query |

The query option is added to Nushell's `cl`, which its `c` alias uses, and to
the shared `dir-picker` command. The existing Zsh wrapper receives the shared
presentation and ordering changes; adding a query flag to that wrapper is
outside this Nushell-focused refactor.

## Current behavior and fzf options

The source and deployed versions of both pickers and shell wrappers were
byte-identical when inspected on 2026-10-07.

[`file-picker.sh`](../private_dot_config/my-scripts/bin/executable_file-picker.sh)
builds rows with a hidden absolute path and an eza display row separated by an
ASCII unit separator. At lines 130–132, it passes `--with-nth 2` to display the
eza row and `--accept-nth 1` to return the absolute path. It has no `--nth`, so
the entire displayed row is searchable, including metadata, relative path
components, and any symlink target. It has no `--exact`, so ordinary queries
use fuzzy matching. `--query` only seeds the initial text. Its `--no-sort`
preserves input order while searching.

[`dir-picker`](../private_dot_config/my-scripts/bin/executable_dir-picker)
currently enumerates immediate child directories and sorts by creation time,
falling back to modification time. It includes hidden directories and symlinks
to directories, excludes regular files and dangling links, and prepends a
synthetic `../` parent candidate. Its fzf invocation uses `--no-sort`, with a
manual Ctrl-S relevance toggle. It preserves actual paths through NUL and JSON
framing and retains symlink paths rather than resolving their destinations.

[`alias.nu`](../private_dot_config/nushell/alias.nu) treats a supplied `cl`/`c`
argument as direct navigation; only the argument-free form opens the picker.
After navigating, it runs `ezam`. The Zsh `cv`/`c` wrapper also navigates
directly when given a nonempty argument and uses NUL output for selection.

The relevant fzf options are:

| Option | Responsibility |
| --- | --- |
| `--query TEXT` | Initial query text |
| `--delimiter` | Candidate field boundaries |
| `--with-nth` | Which fields are displayed |
| `--nth` | Which displayed fields are searched |
| `--accept-nth` | Which original fields are returned on selection |
| `--sort` | Rank matches by score |
| `--tiebreak=index` | Preserve input order when scores tie |
| `--read0`, `--print0` | NUL-framed candidate input and selected output |
| `--ansi` | Interpret display colors |

When `--with-nth` is present, `--nth` indexes the transformed display fields.
`--accept-nth` still identifies original fields. See the
[fzf 0.74.4 manual](https://raw.githubusercontent.com/junegunn/fzf/v0.74.4/man/man1/fzf.1)
and [fzf search syntax](https://github.com/junegunn/fzf#search-syntax).

## Proposed refactoring

1. Keep Python as the shared candidate enumerator and path owner. Replace
   creation-time collection with each candidate directory's modification time,
   following directory symlinks for metadata while retaining their paths, keeping
   existing inclusion rules and deterministic name ordering for equal times.
2. Represent a candidate with a stable numeric identifier, its actual path,
   its matchable name, and its display metadata. Keep actual paths in Python;
   return an identifier from fzf and look up the path rather than parsing a
   decorated display row.
3. Render size, modification date/time, icons, and symlink information in
   Python. Separate metadata and name into distinct fields. For example, an
   original record `ID<TAB>METADATA<TAB>NAME<TAB>SYMLINK_INFO` can use
   `--with-nth=2.. --nth=2 --accept-nth=1`: display metadata, name, and symlink
   information, search only the name, and return the original ID. Keep icons
   and symlink target text outside the name field. Escape display control
   characters and backslashes so unusual names cannot alter field boundaries
   or terminal presentation;
   selection must still retain the actual path.
4. Feed candidates in the chosen empty-query order, enable `--sort`, and use
   `--tiebreak=index`. fzf preserves input order for an empty query and ranks
   matches once text is entered. Equal scores retain recency order. Clearing
   the query restores the input order. Remove the manual sorting toggle so it
   cannot disable the requested automatic score ordering.
5. Add `--query` to the shared script and Nushell wrapper, preserving direct
   navigation when the wrapper's option is absent. When the option is present,
   browse the supplied PATH or current directory, passing the initial text to
   fzf. Match the file picker's 60% height, reverse layout, and colors. Preserve
   fzf's normal extended syntax and smart-case behavior. No query-change hook
   or external sort operation is needed while typing. Do not copy the file
   picker's newline-based `stat`/`paste` pipeline into the directory picker.
6. Revise the current tests that enforce birth-time order and unchanged order
   while filtering. Verify modification-time order, score order after typing,
   restoration after clearing, metadata exclusion, tied scores, cancellation,
   directory symlinks, and existing unusual-name path round trips. Verify the
   Nushell and Zsh wrappers according to the chosen CLI contract.

The metadata timestamp describes the same time used for recency. For a
directory symlink, both use target-directory modification time. Symlink
identification and display information must remain separate from the actual
navigation path.

Routine presentation assumptions are human-readable entry sizes, local-time
modification dates, an explicit Modified label, and safe escaped names. The
existing single-selection, error, cancellation, listing-after-navigation, and
JSON/NUL output contracts are retained. Equal modification times use name
ordering; equal match scores use input order. Negative-only queries have equal
match scores and therefore keep input order.

These implementation choices are readily reversible; an ADR is not justified
at this stage. Confirmed terminology is recorded in [GLOSSARY.md](../GLOSSARY.md).

## Verification of the proposed fzf behavior

On installed fzf 0.74.4, controlled NUL-framed records with distinct metadata
and name fields were tested with ambient fzf defaults disabled.

- Empty-query filtering preserved input order.
- Fuzzy query `abc` matched both consecutive and scattered name characters,
  ordered by fzf score rather than input order.
- A query matching only the displayed date produced no results.
- A separate literal-substring experiment excluded scattered-character names;
  this option was investigated but the user chose fuzzy matching.
- Automated terminal checks accepted the first input candidate with an empty
  query, the highest-scoring candidate after entering a single character or a
  longer fuzzy query, and the first input candidate again after clearing it.

These were mechanism checks, not tests of a completed picker refactor. No
picker implementation or deployed configuration changed during this interview.

## Review boundary

Both interview rounds are settled, and the user confirmed shared understanding
and approved the local documentation merge on 2026-10-07. This change saves the
plan and vocabulary; it does not implement the runtime refactor. Implementation,
push, and deployment remain separate actions.

## Managed-file boundaries for later implementation

| Chezmoi source | Exact deployed target |
| --- | --- |
| `private_dot_config/my-scripts/bin/executable_dir-picker` | `/home/vimkim/.config/my-scripts/bin/dir-picker` |
| `private_dot_config/nushell/alias.nu` | `/home/vimkim/.config/nushell/alias.nu` |
| `private_dot_config/my-scripts/zsh/aliases.zsh` | `/home/vimkim/.config/my-scripts/zsh/aliases.zsh` |

Only the shared script and Nushell wrapper require runtime edits under this
plan; the Zsh source/target pair is listed for existing-wrapper regression
verification. Documentation and test files are excluded from chezmoi
deployment. Any later deployment must verify and apply each concrete target
separately.
