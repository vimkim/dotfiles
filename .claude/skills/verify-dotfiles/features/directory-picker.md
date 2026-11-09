# Directory picker

`c` with no arguments opens an fzf picker over the current directory's child directories, newest first, with `../` on top. Typing filters by directory name. Enter moves the shell into the selected directory, and Escape leaves the directory unchanged. See `docs/directory-picker.md` for the full behavior.

## Sub-features

- `picker-open` lists `../` first, then child directories newest first.
- `picker-filter` fuzzy-matches the typed query against directory names only.
- `picker-accept` changes the shell's own working directory on Enter.
- `picker-cancel` keeps the working directory on Escape or Ctrl-C.
- `picker-direct` makes `c PATH` navigate without opening the picker (Nushell keeps `--query` for picker mode).

## How to get to it (user POV)

- Type `c` in Nushell, Bash, or Zsh.
- In Nushell, type `c --query TEXT` or `cl`.
- Type `c PATH` to navigate directly.

## Driving it with drive.py

Preconditions:

- Fixture: `mkdir -p "$RUN/work/picker/alpha-old" "$RUN/work/picker/beta-new" && touch -d 2020-01-01 "$RUN/work/picker/alpha-old"`.

- **Open and order.** Open the picker. Run `"$S/drive.py" "$RUN" --shell nu --label nu-picker-accept --cwd "$RUN/work/picker" 'keys:c\r' 'expect:beta-new' 'keys:alpha' 'expect:1/3' 'keys:\r' 'cmd:$env.PWD'`. In `nu-picker-accept.txt`, the picker rows show `../`, then `beta-new` (today), then `alpha-old` (2020).
- **Filter and accept.** In the same drive, `alpha` narrows the count to `1/3`, and Enter accepts. The final `cmd:$env.PWD` output ends in `/work/picker/alpha-old`.
- **Cancel.** Run `"$S/drive.py" "$RUN" --shell nu --label nu-picker-cancel --cwd "$RUN/work/picker" 'keys:c\r' 'expect:beta-new' 'keys:\x1b' 'cmd:$env.PWD'`. The cwd still ends in `/work/picker`.
- **Bash and Zsh.** Repeat the accept drive with `--shell bash` or `--shell zsh`, labels `bash-picker-accept` and `zsh-picker-accept`, and `cmd:pwd` as the last step. The output ends in `/work/picker/alpha-old`.
- **Proof.** Keep the `.txt` that shows the picker rows and the final cwd line, and the `.json` with `ok` on every step.

## Gotchas

- Each fixture directory's modification time decides its order. Creating a child inside `alpha-old` after the `touch -d` makes it the newest again.
- The prompt shortens long paths, so read the cwd from the `cmd:$env.PWD` or `cmd:pwd` output, not from the prompt line.
- fzf asks the terminal for the cursor position and the bracketed paste mode. `drive.py` answers both. A drive that hangs right after `keys:c\r` points at a new terminal query that the driver does not answer yet; inspect the `.typescript`.
- After Enter, `c` prints a directory listing before the prompt returns, so the next `cmd` step waits for that prompt.
