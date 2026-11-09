# Sorted listing family

The sorted listing family prints a directory's entries in the order its name promises, with details and hidden entries, from any of the three shells. See `docs/ls-helper-family.md` and the glossary entry **Sorted listing family**.

## Sub-features

- `listing-time` makes `ls-by-time` list the most recently modified entry first (the glossary's **Listing time**).
- `listing-size` makes `ls-by-size` list the largest entry first, and `--reverse` lists the smallest first.
- `listing-name` makes `ls-by-name` use eza's case-insensitive natural name order.
- `listing-filters` makes `ls-dirs` show directories only and `ls-files` show files only.
- `listing-paging` adds a pager only when output exceeds one screen. `--no-pager` keeps output in scrollback.

## How to get to it (user POV)

- Type `ls-by-time`, `ls-by-size`, `ls-by-name`, `ls-by-extension`, `ls-tree`, `ls-dirs`, or `ls-files` with an optional path.
- `l` and `c` show `ls-one-page` output.

## Driving it with drive.py

Preconditions:

- Fixture: `mkdir -p "$RUN/work/listing" && cd "$RUN/work/listing" && printf 'x%.0s' {1..5000} > big.txt && echo hi > small.md && touch -d 2021-01-01 big.txt && touch -d 2023-01-01 small.md && mkdir sub`, run from the agent's Bash.

- **By time.** Run `"$S/drive.py" "$RUN" --shell nu --label nu-listing-time --cwd "$RUN/work/listing" 'cmd:ls-by-time --no-pager'`. The entries appear as `sub` (today), `small.md` (2023), then `big.txt` (2021).
- **By size.** Run `"$S/drive.py" "$RUN" --shell nu --label nu-listing-size --cwd "$RUN/work/listing" 'cmd:ls-by-size --no-pager' 'cmd:ls-by-size --no-pager --reverse'`. In the first output, `big.txt` (5.0k) comes before `small.md` (3). The second reverses them.
- **Filters.** Run `"$S/drive.py" "$RUN" --shell bash --label bash-listing-filters --cwd "$RUN/work/listing" 'cmd:ls-dirs --no-pager' 'cmd:ls-files --no-pager'`. The first output lists only `sub`. The second lists only the two files.
- **Proof.** Keep each `.txt`. In each step's `output`, the order of the entry lines is the proof. Also keep `cmd:which ls-by-time | get path.0`, which shows the helper resolving inside `$RUN/home`.

## Gotchas

- Without `--no-pager`, a listing taller than the terminal opens `less`, and the `cmd` step waits for a prompt that never comes. Pass `--no-pager`, or send `keys:q`.
- eza marks files that have extended attributes with `@`. The column is not part of the order.
- The drive's terminal is 40 rows by default. Paging tests need more entries than that, or `--rows`.
