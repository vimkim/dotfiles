# Dotfiles verification map

This directory is the maintained source for verifying what a user meets after applying these dotfiles. Read this index, then use the matching feature file as the recipe. `S` and `RUN` are the variables from [`../SKILL.md`](../SKILL.md).

## Baseline preconditions

- A run made by `"$S/launch"` from the checkout under test, and `"$S/doctor" "$RUN"` exits 0.
- Seed fixtures under `$RUN/work/<feature>/` with plain `mkdir`, `touch -d`, and `printf` from the agent's shell. The disposable home holds only what the source applies.
- Drive only runs that this verification created.

## Driving conventions

- Drive Nushell first. It is the shell Herdr panes open. Then drive Bash and Zsh where the feature file lists them.
- Give every drive a `--label` of `<shell>-<feature-id>`, so evidence files name what they prove.
- Treat commands in feature files as literal. Keep quoted names and flags unchanged.
- Restore the home after a journey that edits targets (`"$S/in-run" "$RUN" chezmoi apply --force --exclude=externals`), or launch a fresh run before driving the next feature. Revert every probe edit made in the checkout.

## Proof and skip reporting

The proof standards in [`../SKILL.md`](../SKILL.md#4-evidence) apply. In addition:

- Record the feature ID and the shell for each evidence file.
- When a precondition cannot be met, report the attempted command and the unmet precondition as a failure. Leave the journey as written.
- A feature verified in one shell is unverified in the others until each one is driven.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then has exactly four H2 sections, in this order:

1. `Sub-features`: short IDs with one line each.
2. `How to get to it (user POV)`: every user entry point.
3. `Driving it with drive.py`: starts with `Preconditions:`, then labeled bullets. Each bullet pairs a user action with an exact command and its observable result.
4. `Gotchas`: traps that can waste or invalidate a run.

Keep implementation details out of the map. Name only user paths, required state, commands, and observable proof.

## Features

- [Apply the dotfiles](./apply.md): `chezmoi apply` builds the home, templates render, retired targets go, and re-apply converges.
- [Shell startup](./shell-startup.md): Nushell, Bash, and Zsh start from the applied home with the helpers on PATH.
- [Directory picker](./directory-picker.md): `c` opens the fzf picker, `c PATH` and `c --query` cover the rest, and the shell lands in the chosen directory.
- [Sorted listing family](./sorted-listing.md): `ls-by-*` order entries as named, page only when needed, and `l`, `sl`, and `c` preview one screen.
- [Apply only unmodified targets](./apply-unmodified.md): `chezmoi-apply-unmodified` applies untouched targets and skips local edits, deletions, and targets without last-write history.

Not yet mapped: `find-project`, `dir-history` and `ch`, `dir-bookmark`, `work-todo`, `ports` (`list-ports.py`), the `just` picker (`just-pick-and-print.nu`), `my-skill-check`, `prv`, `difpr`, `gh-html`, `html-serve`, `daily-update --remind`, the `claude-auth-renewal` reminder, and the Nushell aliases in `alias.nu`. Run `/maintain-verification-skill` to add them.
