# Dirpick installation and updates

[Dirpick](https://github.com/vimkim/dirpick) is a native terminal workbench for
finding files, directories, and text. It uses the Catppuccin Mocha theme.
Project root is the default scope. F7 switches between Project root and the
directory where Dirpick was launched.

## Initialize once

Install Git and a current Rust/Cargo toolchain before applying these dotfiles.
Rust builds also require a system C compiler and linker. The repository's
other bootstrap scripts have their own prerequisites.

```sh
chezmoi init --apply vimkim/dotfiles
```

The `run_once_after_install-dirpick.sh` script invokes the managed
`~/.config/my-scripts/bin/install-dirpick` command after files are deployed.
The installer clones `vimkim/dirpick` into `~/gh/dirpick` when that path is absent.
It runs this command from the checkout:

```sh
cargo install --locked --path . --root "$HOME/.local" --bin dirpick
```

The resulting `~/.local/bin/dirpick` is on the managed Bash, Zsh, and Nushell PATH.
The explicit installation root also overrides `CARGO_INSTALL_ROOT`.
The installer finds Cargo on PATH, or in `~/.cargo/bin` before shell initialization.
It builds a release binary and checks `dirpick --version`.

Existing installations of these dotfiles receive this bootstrap on their next
`chezmoi apply`. A successful run is recorded once. A failed run remains eligible
for retry. Neither `daily-update` nor `chezmoi-apply-unmodified` executes run scripts.
When deploying through the helper, run the installer explicitly for initial setup.

The installer preserves occupied paths, symlinks, linked worktrees, dirty
checkouts, detached HEAD, other branches, and unexpected origins. It accepts a
clean primary `main` checkout with the HTTPS or SSH origin for `vimkim/dirpick`.
It does not fetch or change existing checkout history. Cargo retains ownership
tracking, without forcing replacement of unrelated binaries.

After correcting a prerequisite or checkout problem, retry with:

```sh
install-dirpick
```

If bootstrap failed, another `chezmoi apply` also retries it.

## Use Dirpick

```sh
dirpick
```

Nushell imports the managed `~/.config/nushell/dirpick.nu` module on startup.
Open a new shell after deployment, or import it into the current shell:

```nu
use ~/.config/nushell/dirpick.nu dp
dp
```

Ctrl-G selects a directory and changes the shell's directory. Esc cancels without
changing the shell directory. The wrapper checks Dirpick's JSON action before
executing `cd`. It preserves spaces, tabs, and newlines in directory paths.
The module uses Dirpick v0.1's `--print-nu-wrapper` protocol and is managed here,
so installation does not overwrite local shell configuration.

## Update

```sh
daily-update
```

The `tool:dirpick` step fetches published `main`, requires a clean primary
checkout tracking `origin/main`, and requires the expected GitHub origin.
It skips ahead or diverged history. After a fast-forward, it invokes the same
installer. Cargo rebuilds changed sources even if the crate version is unchanged.
A build failure retains the previously installed binary. A later run retries
installation even when no new commits are available.

Daily update reports checkout skips and build failures through its existing
summary and exit status. See [daily-update policy](daily-update.md) for details.

## Checks

```sh
bash -n private_dot_config/my-scripts/bin/executable_install-dirpick
bash -n .chezmoiscripts/run_once_after_install-dirpick.sh
shellcheck private_dot_config/my-scripts/bin/executable_install-dirpick \
  .chezmoiscripts/run_once_after_install-dirpick.sh \
  private_dot_config/my-scripts/bin/executable_daily-update
python3 -B -m unittest discover -s tests -p test_install_dirpick.py -v
python3 -B -m unittest discover -s tests -p test_daily_update.py -v
```

Tests use disposable homes, local Git remotes, and controlled command substitutes.
Real chezmoi checks deployment ordering and run-once retry behavior. Real Cargo
builds a small fixture to check replacement and failed-build preservation.
Real Nushell checks directory changes, cancellation, validation, and optional
module imports. Tests do not run live toolchain upgrades or update installed skills.
