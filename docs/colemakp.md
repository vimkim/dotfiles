# Installing the Colemak Programmer Layout

`colemakp` is a standalone XKB layout based on the system `us(colemak)`
layout. It keeps programming symbols unshifted on the number row, keeps braces
unshifted, and uses `Ctrl` instead of `Caps Lock`.

The layout is intentionally stored in `~/.config/xkb/symbols/colemakp`, not in
`~/.config/xkb/symbols/us`. XKB searches user configuration before system
configuration, so a user-owned `symbols/us` can hide
`/usr/share/X11/xkb/symbols/us`. Older XKB consumers, including some statically
packaged Wayland applications, can then fail to resolve `us(colemak)` and start
without a usable keymap.

## Files

- `private_dot_config/xkb/symbols/colemakp` defines the layout and inherits
  from the system `us(colemak)` section.
- `private_dot_config/xkb/rules/evdev.xml` makes the layout discoverable to
  desktop configuration tools.
- `private_dot_config/private_kxkbrc` selects `colemakp` in KDE Plasma.
- `private_dot_local/bin/executable_install-colemakp` validates and applies
  those three managed files.

The XKB lookup chain is:

```text
KDE layout=colemakp, variant=<none>
  -> ~/.config/xkb/symbols/colemakp (default "basic" section)
  -> /usr/share/X11/xkb/symbols/us ("colemak" section)
  -> colemakp programming-key overrides
```

## Install

First install the helper itself from the chezmoi source repository:

```bash
chezmoi apply ~/.local/bin/install-colemakp
```

Preview the exact changes:

```bash
install-colemakp --dry-run
```

Install the layout:

```bash
install-colemakp
```

The helper validates the keymap before applying anything. It prefers `xkbcli`
and falls back to `xkbcomp`. On Fedora, install the preferred validator with:

```bash
sudo dnf install libxkbcommon-utils
```

If the obsolete `~/.config/xkb/symbols/us` from the earlier colemakp setup is
present, the helper verifies its exact checksum and moves it to
`~/.config/xkb/symbols/us.pre-standalone-colemakp`. It refuses to touch a
different file at that path, because that may contain unrelated custom XKB
work. If applying the managed files fails, the helper restores the legacy file.

Log out and back in after installation so Plasma reloads the XKB registry and
keymap.

## Verify

After logging back in, verify the active KDE configuration:

```bash
kreadconfig6 --file kxkbrc --group Layout --key LayoutList
kreadconfig6 --file kxkbrc --group Layout --key VariantList
```

The first command should print `colemakp`; the second should print an empty
line. Confirm that no user-owned `us` symbols file is shadowing the system
layout:

```bash
test ! -e ~/.config/xkb/symbols/us
```

Finally, start a native Wayland application that consumes the compositor
keymap, such as WezTerm:

```bash
wezterm
```

Warnings about an unknown Compose keysym such as `dead_hamza` are a separate
version mismatch in statically packaged applications. The fatal colemakp
problem is fixed when `us(colemak)` resolves and the keymap compiles.

## Recovery

If Plasma cannot load the new layout, switch back to the system Colemak layout
in KDE System Settings, or change the managed `kxkbrc` values to:

```ini
LayoutList=us
VariantList=colemak
```

Then apply only that file and log out:

```bash
chezmoi apply ~/.config/kxkbrc
```

Do not restore the old file as `~/.config/xkb/symbols/us` unless it has first
been rewritten so it cannot shadow the system `us` symbols file.

References:

- [libxkbcommon custom configuration](https://xkbcommon.org/doc/current/custom-configuration.html)
- [libxkbcommon debugging tools](https://xkbcommon.org/doc/current/debugging.html)
