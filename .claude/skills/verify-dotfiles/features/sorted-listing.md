# Sorted listing family

The sorted listing family prints a directory's entries in the order its name promises, with details and hidden entries, from any of the three shells. `l`, `sl`, and `c` show a one-screen preview instead. See `docs/ls-helper-family.md` and the glossary entries **Sorted listing family**, **Listing time**, and **Automatic listing paging**.

## Sub-features

- `listing-time` makes `ls-by-time` list the most recently modified entry first.
- `listing-size` makes `ls-by-size` list the largest entry first, and `--reverse` flips the order.
- `listing-name` makes `ls-by-name` sort case-insensitively in natural order (`file2` before `file10`).
- `listing-extension` makes `ls-by-extension` sort by extension, with extensionless entries first.
- `listing-tree` makes `ls-tree` show two levels.
- `listing-filters` makes `ls-dirs` show directories only and `ls-files` show files only.
- `listing-paging` opens `less` only for the seven sorted commands, only on a terminal, and only when output exceeds one screen. `--no-pager` and pipes never page.
- `listing-preview` makes `l`, `sl`, and `c DIR` show at most 70% of the terminal rows, ending with `... N entries skipped.`

## How to get to it (user POV)

- Type `ls-by-time`, `ls-by-size`, `ls-by-name`, `ls-by-extension`, `ls-tree`, `ls-dirs`, or `ls-files` with an optional path.
- Type `l`, `sl`, or `ls-one-page` for the preview, and `ls-full` or `lsf` for every entry without a pager.
- `c DIR` and an accepted `c` picker print the same preview.

## Driving it with drive.py

Preconditions, run from the agent's Bash:

- `L="$RUN/work/listing"; mkdir -p "$L/sub/inner" && cd "$L" && printf 'x%.0s' {1..5000} > big.txt && echo hi > small.md && touch sub/inner/deep.txt && touch -d 2021-01-01 big.txt && touch -d 2023-01-01 small.md`
- `mkdir -p "$RUN/work/names" && touch "$RUN/work/names/"{Banana.txt,apple.txt,file10,file2}`
- `mkdir -p "$RUN/work/many" && cd "$RUN/work/many" && touch file-{001..450}`

- **Order.** Run `"$S/drive.py" "$RUN" --shell nu --label nu-listing-order --cwd "$L" 'cmd:ls-by-time --no-pager' 'cmd:ls-by-size --no-pager' 'cmd:ls-by-size --no-pager --reverse'`. By time, the order is `sub`, `small.md` (1 Jan 2023), `big.txt` (1 Jan 2021). By size, `big.txt` (5.0k) comes before `small.md` (3), and `--reverse` flips them.
- **Filters, name, extension, tree.** Run `"$S/drive.py" "$RUN" --shell bash --label bash-listing-filters --cwd "$L" 'cmd:ls-dirs --no-pager' 'cmd:ls-files --no-pager' "cmd:ls-by-name $RUN/work/names" 'cmd:ls-by-extension --no-pager' 'cmd:ls-tree --no-pager'`. `ls-dirs` shows only `sub`, and `ls-files` shows only the two files. The names come out as `apple.txt`, `Banana.txt`, `file2`, `file10`. Extension order is `sub`, `small.md`, `big.txt`. The tree shows `sub` and `inner`, but not `deep.txt`.
- **Paging.** Run `"$S/drive.py" "$RUN" --shell bash --label bash-listing-paging --cwd "$RUN/work/many" 'cmd:ls-by-name | wc -l' 'keys:ls-by-name\r' 'expect:file-03\d' 'keys:G' 'expect:\(END\)' 'keys:q' 'cmd:echo back' 'cmd:ls-by-name --no-pager | tail -n1'`. The pipe prints `450` with no pager. The bare command opens `less`, `G` reaches `(END)`, and `q` returns to the prompt, so `back` prints. `--no-pager` ends at `file-450`.
- **Preview.** Run `"$S/drive.py" "$RUN" --shell zsh --label zsh-listing-l --cwd "$RUN/work/many" 'cmd:l' 'cmd:lsf | wc -l'` and `"$S/drive.py" "$RUN" --shell nu --label nu-listing-c --cwd "$RUN/work" 'cmd:c many' 'cmd:$env.PWD' 'cmd:sl'`. `l`, `c many`, and `sl` each show a grid of 27 rows (70% of 40) ending in `... 342 entries skipped. Run ls-full or lsf to view all.`, with no pager. `lsf | wc -l` prints `450`, and the cwd ends in `/work/many`.
- **Proof.** Keep each `.txt` and `.json`. The order of the entry lines in each step's `output` is the proof.

## Gotchas

- A `cmd:` step blocks until its prompt returns, so a listing that opens `less` inside a `cmd:` step times out, and no later `keys:q` can rescue it. Start paged listings with `keys:...\r` plus `expect:`, or pass `--no-pager`. Listings shorter than the screen never block, because `less -F` exits on its own.
- `sub`'s place in the size order depends on the filesystem's directory entry size. On this host's xfs it falls between the two files. Assert only the files' relative order.
- eza appends `@` to the permission string when an entry has extended attributes (SELinux labels here). It is not part of the order. The preview commands hide permissions.
- The drive's terminal is 40 rows by default. Paging and preview limits scale with `--rows`.
