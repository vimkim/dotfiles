# Directory picker search and metadata design

Status: interview in progress. This document records confirmed requirements,
source evidence, and a proposed refactoring plan. Runtime behavior has not
changed. The existing behavior remains documented in [directory-picker.md](directory-picker.md).

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
   creation-time collection with each candidate's modification time, keeping
   existing inclusion rules and deterministic name ordering for equal times.
2. Represent a candidate with a stable numeric identifier, its actual path,
   its matchable name, and its display metadata. Keep actual paths in Python;
   return an identifier from fzf and look up the path rather than parsing a
   decorated display row.
3. Separate metadata and name into distinct fields. For example, an original
   record `ID<TAB>METADATA<TAB>NAME` can use `--with-nth=2.. --nth=2
   --accept-nth=1`: display metadata and name, search only the name, and return
   the original ID. Escape display control characters and backslashes so
   unusual names cannot alter field boundaries or terminal presentation;
   selection must still retain the actual path.
4. Feed candidates in the chosen empty-query order, enable `--sort`, and use
   `--tiebreak=index`. fzf preserves input order for an empty query and ranks
   matches once text is entered. Equal scores retain recency order. Clearing
   the query restores the input order. Remove the manual sorting toggle so it
   cannot disable the requested automatic score ordering.
5. Add `--query` to the shared script and Nushell wrapper, preserving direct
   navigation when the wrapper's option is absent. Choose metadata rendering
   and the combined path/query behavior after the open decisions below are
   answered. Match the file picker's 60% height, reverse layout, and
   colors unless a later requirement changes this routine presentation choice.
   If eza renders directory rows, pass `--list-dirs`; without it, eza can list
   directory contents instead. Do not copy the file picker's newline-based
   `stat`/`paste` pipeline into the directory picker.
6. Revise the current tests that enforce birth-time order and unchanged order
   while filtering. Verify modification-time order, score order after typing,
   restoration after clearing, metadata exclusion, tied scores, cancellation,
   directory symlinks, and existing unusual-name path round trips. Verify the
   Nushell and Zsh wrappers according to the chosen CLI contract.

The metadata timestamp should describe the same time used for recency. The
symlink timestamp policy remains an open decision: current ordering uses the
link itself, whereas target-directory modification time may better describe
changes inside the directory being entered.

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

## Open decisions

Round 1 is settled. Round 2 questions awaiting answers:

- Does recency for a directory symlink use the link's modification time or its
  target directory's modification time?
- Are fzf's usual space-separated terms and query operators desired, or should
  every query character be literal while retaining fuzzy matching?
- Should Python render similar metadata columns, should eza become required
  for exact presentation, or should eza be optional with a Python fallback?
- Should `c PATH --query TEXT` browse PATH with initial text or reject the
  combination?

## Managed-file boundaries for later implementation

| Chezmoi source | Exact deployed target |
| --- | --- |
| `private_dot_config/my-scripts/bin/executable_dir-picker` | `/home/vimkim/.config/my-scripts/bin/dir-picker` |
| `private_dot_config/nushell/alias.nu` | `/home/vimkim/.config/nushell/alias.nu` |
| `private_dot_config/my-scripts/zsh/aliases.zsh` | `/home/vimkim/.config/my-scripts/zsh/aliases.zsh` |

The selected wrapper contract determines whether wrapper edits are needed.
Documentation and test files are excluded from chezmoi deployment. Any later
deployment must verify and apply each concrete target separately.
