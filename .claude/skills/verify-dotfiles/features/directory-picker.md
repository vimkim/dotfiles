# Directory picker

`c` with no arguments opens an fzf picker over the current directory's child directories, with `../` on top and the rest newest first. Typing filters by directory name. Enter moves the shell into the selected directory and prints an `ls-one-page` listing. Escape or Ctrl-C leaves the directory unchanged. `c PATH` navigates directly, and `c --query TEXT` opens the picker with the query already typed. All of this works in Nushell, Bash, and Zsh.

## Sub-features

- `picker-open` lists `../` first, then child directories newest first.
- `picker-filter` fuzzy-matches the typed query against directory names only.
- `picker-accept` changes the shell's own working directory on Enter, then lists it.
- `picker-cancel` keeps the working directory on Escape or Ctrl-C.
- `picker-direct` makes `c PATH` navigate without opening the picker.
- `picker-query` makes `c --query TEXT` open the picker pre-filtered.

## How to get to it (user POV)

- Type `c`, `c PATH`, or `c --query TEXT` in Nushell, Bash, or Zsh.
- In Nushell, `cl` is the same command as `c`. In Bash and Zsh, `cl PATH` changes directory and lists it without a picker.

## Driving it with drive.py

Preconditions:

- Fixture: `mkdir -p "$RUN/work/picker/alpha-old" "$RUN/work/picker/beta-new" && touch -d 2020-01-01 "$RUN/work/picker/alpha-old"`. The `1/3` count needs exactly these two directories.

- **Open, filter, and accept.** Run `"$S/drive.py" "$RUN" --shell nu --label nu-picker-accept --cwd "$RUN/work/picker" 'keys:c\r' 'expect:beta-new' 'keys:alpha' 'expect:1/3' 'keys:\r' 'cmd:$env.PWD'`. The picker rows read `../`, then `beta-new` (today), then `alpha-old` (2020). Typing `alpha` narrows the count to `1/3`. The final output ends in `/work/picker/alpha-old`.
- **Cancel.** Run the same drive with `'keys:c\r' 'expect:beta-new' 'keys:\x1b' 'cmd:$env.PWD'` (label `nu-picker-cancel`), and again with `'keys:\x03'` (label `nu-picker-ctrlc`). Each cwd still ends in `/work/picker`.
- **Direct.** Run `"$S/drive.py" "$RUN" --shell nu --label nu-picker-direct --cwd "$RUN/work/picker" 'cmd:c alpha-old' 'cmd:$env.PWD'`. No picker opens, and the cwd ends in `/work/picker/alpha-old`.
- **Query.** Run `"$S/drive.py" "$RUN" --shell nu --label nu-picker-query --cwd "$RUN/work/picker" 'keys:c --query alpha\r' 'expect:1/3' 'keys:\r' 'cmd:$env.PWD'`. The picker opens at `1/3`, and the cwd ends in `/work/picker/alpha-old`.
- **Bash and Zsh.** Repeat accept, cancel, direct, and query with `--shell bash` and `--shell zsh`, labels `<shell>-picker-<id>`, and `cmd:pwd` as the last step. The results match Nushell's.
- **Proof.** Keep each `.txt` that shows the picker rows and the final cwd line, and each `.json` with `ok` on every step.

## Gotchas

- The product docs lag the source: `docs/directory-picker.md` omits Bash and names the wrong Zsh wrapper and listing command. The shell wrappers live in `private_dot_config/nushell/alias.nu` (`cl`) and `private_dot_config/my-scripts/shell/productivity.sh` (`c`, `cl`, `l`).
- Each fixture directory's modification time sets its order. Creating a child inside `alpha-old` after the `touch -d` makes it the newest again.
- The prompt shortens long paths, so read the cwd from the `cmd:$env.PWD` or `cmd:pwd` output, not from the prompt line.
- fzf asks the terminal for the cursor position and the bracketed paste mode, and `drive.py` answers both. A drive that hangs right after `keys:c\r` points at a new terminal query the driver does not answer yet. Inspect the `.typescript`.
