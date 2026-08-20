# Installing Maple Mono Nerd Font on Fedora

Homebrew supports Maple Mono Nerd Font on Linux. Install it and refresh the
fontconfig cache:

```bash
brew install --cask font-maple-mono-nf
fc-cache -f
```

Verify that fontconfig can find the font:

```bash
fc-match "Maple Mono NF"
```

Fully restart the terminal, then select **Maple Mono NF** in its font settings.

For the version that includes CJK glyphs, install this cask instead:

```bash
brew install --cask font-maple-mono-nf-cn
```

References:

- [Maple Mono downloads](https://font.subf.dev/en/download/)
- [Homebrew package](https://formulae.brew.sh/cask/font-maple-mono-nf)
