# Chezmoi Dotfiles Repository

This directory is the chezmoi source repository. Make configuration changes here,
not directly in the deployed files under `$HOME`.

When working on a dotfile request:

1. Update the corresponding chezmoi source file in this repository.
2. Verify the source change and, where relevant, apply or test the specific managed file.
3. When the work is ready, ask the user: `chezmoi apply, git commit, git push`.

Do not run a broad `chezmoi apply`, commit, or push unless the user explicitly
asks for it. A full apply can overwrite locally modified managed files.
