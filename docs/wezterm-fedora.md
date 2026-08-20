# WezTerm on Fedora KDE through Herdr

This note records the WezTerm startup and keyboard failures diagnosed on this
machine, the fixes kept in this chezmoi repository, and the package switch that
removed the remaining Compose warnings. The important point is that these were
separate failures: KDE window decoration behavior, a stale shell environment,
an XKB include-path collision, and an AppImage/library compatibility mismatch.

## Result

The working configuration is:

- Fedora Linux 44 KDE Plasma on Wayland;
- Herdr `0.8.0`, with `herdr-shell` restoring missing graphical-session
  variables before it starts Nushell;
- a standalone XKB layout named `colemakp`, which includes the system
  `us(colemak)` layout without creating a user-owned `symbols/us` file;
- the official WezTerm Fedora 41 nightly RPMs, version
  `20260820-083501-35680af7`, running against Fedora's system
  `libxkbcommon 1.13.1`.

The Fedora 41 RPM is a package published by the WezTerm project, not a package
built or supported by the Fedora Project. WezTerm's Linux installation guide
says its CI produces Fedora RPMs and that they are likely compatible with other
RPM-based distributions; Fedora 41 is the newest direct-download target listed
there. The nightly assets themselves are mutable. See the
[official Linux installation guide](https://wezterm.org/install/linux.html#installing-on-fedora-and-rpm-based-systems)
and [nightly release](https://github.com/wezterm/wezterm/releases/tag/nightly).

## Failure chain and fixes

### 1. KDE maximization and window decorations

The original visual symptom was a maximized WezTerm window appearing to extend
below KDE's usable work area. The local config forced
`window_decorations = "RESIZE"`, which disables the title bar while retaining
the resize border; the upstream default is `TITLE | RESIZE`, and the windowing
system can override decorations on X11 and Wayland. See WezTerm's
[`window_decorations` reference](https://wezterm.org/config/lua/config/window_decorations.html).

Removing the override restored the default negotiation with KWin. This was a
local mitigation, not proof that WezTerm had calculated the monitor dimensions
incorrectly. It is recorded in dotfiles commit
[`bde4d9d`](https://github.com/vimkim/dotfiles/commit/bde4d9deb40ebf9f55513034e94b1b8fb3c5d307).

### 2. Herdr shells had no graphical-session environment

After the decoration change, starting WezTerm inside a Herdr pane failed with:

```text
ERROR  wezterm_gui > XOpenDisplay failed to open a display. Check the $DISPLAY env var; terminating
```

This was not a monitor-size problem. Locally, the persistent Herdr server was
PID `3041`, had been running since `2026-08-20 13:08:25 +0900`, and was the
ancestor of the affected shells. Its environment did not contain `DISPLAY`,
`WAYLAND_DISPLAY`, `XAUTHORITY`, `XDG_RUNTIME_DIR`, or `XDG_SESSION_TYPE`.
At the same time, the systemd user manager held current KDE values including
`DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0`, and `XDG_SESSION_TYPE=wayland`.
Clearing those variables in a normal shell reproduced the same WezTerm error.

The managed [`herdr-shell`](../private_dot_local/bin/executable_herdr-shell)
now reads `systemctl --user show-environment` once and imports only a missing
value from this allowlist:

```text
DISPLAY
WAYLAND_DISPLAY
XAUTHORITY
XDG_RUNTIME_DIR
XDG_SESSION_TYPE
```

Existing values are never replaced, so an inherited X11 display, SSH-forwarded
`DISPLAY`, or explicitly selected session remains authoritative. If `systemctl`
is absent or the user manager cannot be queried, the wrapper still starts the
shell. Upstream systemd documents `show-environment` as dumping the manager's
effective environment block; `--user` selects the calling user's service
manager. See the official
[`systemctl` manual](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html#Environment%20Commands)
and its [corresponding source](https://github.com/systemd/systemd/blob/main/man/systemctl.xml#L1406-L1414).

The fix and its three regression tests are in dotfiles commit
[`e6098b9`](https://github.com/vimkim/dotfiles/commit/e6098b9027479e3ee539dea3112f409f8dc4cdea).
The tests verify import of missing values, preservation of inherited values,
and graceful behavior when `systemctl` fails.

### 3. A user `symbols/us` file shadowed the system US layout

Once WezTerm could reach the display, its bundled XKB consumer exposed a second
failure: the custom file `~/.config/xkb/symbols/us` was found before the system
file while the custom section itself contained `include "us(colemak)"`. With
the older bundled library, that name resolved back through the user `us` file
instead of reliably reaching the system `colemak` section, so WezTerm could not
compile a usable keymap.

This lookup behavior follows libxkbcommon's documented search order:
`$XDG_CONFIG_HOME/xkb` (normally `~/.config/xkb`) precedes the system XKB root.
Its custom-layout guide explicitly warns about user files that reuse system
names, recommends independent names, and documents compatibility differences
for versions before 1.9. See the official
[include-path documentation](https://xkbcommon.org/doc/current/group__include-path.html)
and [custom-configuration guide](https://xkbcommon.org/doc/current/custom-configuration.html#using-system-file-names).

The portable fix was to make `colemakp` a standalone layout:

```text
KDE layout=colemakp, variant=<none>
  -> ~/.config/xkb/symbols/colemakp (default "basic" section)
  -> /usr/share/X11/xkb/symbols/us ("colemak" section)
  -> colemakp programming-symbol overrides
```

The managed files are:

- [`symbols/colemakp`](../private_dot_config/xkb/symbols/colemakp), whose
  default `basic` section includes `us(colemak)`;
- [`rules/evdev.xml`](../private_dot_config/xkb/rules/evdev.xml), which exposes
  `colemakp` as a layout;
- [`kxkbrc`](../private_dot_config/private_kxkbrc), which selects
  `LayoutList=colemakp` with an empty variant;
- [`install-colemakp`](../private_dot_local/bin/executable_install-colemakp),
  which validates and applies the layout without overwriting an unknown
  `~/.config/xkb/symbols/us` file.

The layout fix is dotfiles commit
[`bf71271`](https://github.com/vimkim/dotfiles/commit/bf7127152736f9153d46b08c59365b1a8a6afde1),
and the safe installer is
[`4b44ce2`](https://github.com/vimkim/dotfiles/commit/4b44ce25b28d50e50a5130629cb2d5aab7c7ef00).
See also [the dedicated Colemak programmer-layout note](colemakp.md).

### 4. `dead_hamza` came from mixed-age Compose data and library code

With the display and keymap failures fixed, the Linuxbrew WezTerm started but
printed five errors twice:

```text
xkbcommon: ERROR: /usr/share/X11/locale/en_US.UTF-8/Compose:1661:1: unrecognized keysym "dead_hamza" on left-hand side
```

This was a non-fatal compatibility warning, independent of `colemakp`.
Fedora 44's system Compose file contains five Arabic sequences whose left-hand
side begins with `dead_hamza`. Libxkbcommon's release notes show that the
`XKB_KEY_dead_hamza` name was added in version 1.6.0; libxkbcommon is also the
component that parses Compose files. See the upstream
[1.6.0 release notes](https://github.com/xkbcommon/libxkbcommon/blob/xkbcommon-1.6.0/NEWS#L57-L66)
and [Compose API documentation](https://xkbcommon.org/doc/current/group__compose.html).

The installed Linuxbrew formula came from the WezTerm project's own tap at
commit `13145a664b0ca8d000a4c183684e663307273699`. That formula installs an
Ubuntu 20.04 AppImage directly as `bin/wezterm`; its stable and nightly URLs
are visible in the
[formula source](https://github.com/wezterm/homebrew-wezterm-linuxbrew/blob/13145a664b0ca8d000a4c183684e663307273699/Formula/wezterm.rb).
The [pinned upstream template](https://github.com/wezterm/wezterm/blob/35680af7a450564b66d6475f652f1495622b6b03/ci/wezterm-linuxbrew.rb.template#L1-L16)
shows the same AppImage passthrough.
WezTerm describes AppImage as a self-contained single-file format in its
[official Linux guide](https://wezterm.org/install/linux.html#installing-on-linux-using-appimage).

Local extraction established the exact boundary:

- the outer Linuxbrew `wezterm` file was a static PIE AppImage launcher;
- its SquashFS contained `usr/lib/libxkbcommon.so.0`;
- the inner `usr/bin/wezterm-gui` declared `libxkbcommon.so.0` as a dynamic
  dependency, which the AppImage satisfied with that bundled copy;
- the bundled library's `xkb_keysym_from_name("dead_hamza")` returned `0`,
  while Fedora's system library returned `0xfe8d`;
- the bundled library still returned a non-null Compose table, confirming that
  these messages were non-fatal warnings rather than a total Compose failure;
- Fedora's system library recognized the name, and
  `xkbcli compile-compose --locale en_US.UTF-8` succeeded.

Therefore the cause on this machine was the AppImage's older bundled
libxkbcommon reading Fedora 44's newer system Compose data. A similar exact
warning has also been reported against another self-contained WezTerm package
on Fedora in upstream issue
[#7313](https://github.com/wezterm/wezterm/issues/7313); that issue is
corroboration, not the basis of the local diagnosis.

The official Fedora 41 nightly RPM solved the mismatch. Locally,
`/usr/bin/wezterm-gui` dynamically resolved both `libxkbcommon.so.0` and
`libxkbcommon-x11.so.0` from `/lib64`, and RPM ownership traced the former to
Fedora package `libxkbcommon-1.13.1-2.fc44.x86_64`. The GUI then launched with
no `dead_hamza`, `XOpenDisplay`, or keymap errors.
This matches WezTerm's pinned RPM build logic, which installs the distro's
`libxkbcommon-devel` and declares `libxkbcommon` and `libxkbcommon-x11` as GUI
runtime requirements in
[`ci/deploy.sh`](https://github.com/wezterm/wezterm/blob/35680af7a450564b66d6475f652f1495622b6b03/ci/deploy.sh#L164-L226).

## Package switch and rollback

### Switch from the preserved Linuxbrew AppImage to the RPM

The direct nightly URLs are mutable and will install whatever WezTerm currently
publishes. These are the same two URLs used in the successful local DNF
transaction:

```bash
sudo dnf install -y \
  https://github.com/wezterm/wezterm/releases/download/nightly/wezterm-common-nightly-fedora41.rpm \
  https://github.com/wezterm/wezterm/releases/download/nightly/wezterm-gui-nightly-fedora41.rpm

/usr/bin/wezterm --version
brew unlink wezterm/wezterm-linuxbrew/wezterm

command -v wezterm
wezterm --version
```

Expected paths are `/usr/bin/wezterm` and `/usr/bin/wezterm-gui`. On
`2026-08-21`, the installed packages were:

```text
wezterm-common-20260820_083501_35680af7-1.fedora41.x86_64
wezterm-gui-20260820_083501_35680af7-1.fedora41.x86_64
```

The version suffix identifies upstream WezTerm commit
[`35680af7`](https://github.com/wezterm/wezterm/commit/35680af7). The two RPM
files retained in the local DNF cache had these SHA-256 hashes:

```text
568d1799a8470c740fe35a3b6d12a18deb89b0e656a8d07164de4496bc548a56  wezterm-common-nightly-fedora41.rpm
0fe07bca094c7d36b6179f2d3fec44b008d2d833c3aac3ee6106c683ee6fb410  wezterm-gui-nightly-fedora41.rpm
```

Those hashes describe the observed `20260820` artifacts only; they must not be
used to validate a later download from the mutable `nightly` URLs.

### Roll back to the existing Linuxbrew AppImage

The old Cellar installation was deliberately retained. To remove the RPM and
restore its link:

```bash
brew link wezterm/wezterm-linuxbrew/wezterm
sudo dnf remove wezterm-common wezterm-gui

command -v wezterm
wezterm --version
```

The preserved binary is
`/home/linuxbrew/.linuxbrew/Cellar/wezterm/HEAD/bin/wezterm`, version
`20260117-154428-05343b38`. Rolling back also restores the `dead_hamza`
warnings unless the AppImage itself is replaced by a build with compatible XKB
data and library code.

## Verification commands

### Herdr environment repair

Show the KDE values available from the user manager:

```bash
systemctl --user show-environment \
  | grep -E '^(DISPLAY|WAYLAND_DISPLAY|XAUTHORITY|XDG_RUNTIME_DIR|XDG_SESSION_TYPE)='
```

Simulate the missing environment and verify that `herdr-shell` restores it:

```bash
env -u DISPLAY \
    -u WAYLAND_DISPLAY \
    -u XAUTHORITY \
    -u XDG_RUNTIME_DIR \
    -u XDG_SESSION_TYPE \
    ~/.local/bin/herdr-shell -c \
    'print $"DISPLAY=($env.DISPLAY) WAYLAND_DISPLAY=($env.WAYLAND_DISPLAY) XDG_SESSION_TYPE=($env.XDG_SESSION_TYPE)"'
```

Expected local output:

```text
DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_SESSION_TYPE=wayland
```

Run the regression tests:

```bash
python3 -m unittest tests.test_herdr_shell -v
```

### XKB layout and Compose data

```bash
test ! -e ~/.config/xkb/symbols/us

XDG_CONFIG_HOME="$PWD/private_dot_config" \
  xkbcli compile-keymap --layout colemakp >/dev/null

xkbcli compile-compose --locale en_US.UTF-8 >/dev/null

kreadconfig6 --file kxkbrc --group Layout --key LayoutList
kreadconfig6 --file kxkbrc --group Layout --key VariantList
```

The keymap and Compose commands should return zero. KDE should report
`colemakp` followed by an empty variant.

### WezTerm package and linkage

```bash
command -v wezterm
wezterm --version
rpm -q wezterm-common wezterm-gui libxkbcommon
ldd /usr/bin/wezterm-gui | grep xkbcommon
```

The relevant linkage should resolve to Fedora paths:

```text
libxkbcommon-x11.so.0 => /lib64/libxkbcommon-x11.so.0
libxkbcommon.so.0 => /lib64/libxkbcommon.so.0
```

For an end-to-end interactive check from a Herdr pane, run the following and
close the probe window after it appears:

```bash
wezterm start --always-new-process --class HerdrDisplayProbe
```

No `XOpenDisplay`, XKB keymap, panic, or `dead_hamza` message should be printed.

## Local verification — 2026-08-21

All entries in this section are local observations, not upstream guarantees.

| Item | Observed value |
| --- | --- |
| OS | Fedora Linux 44 KDE Plasma Desktop Edition |
| Session | Wayland; `DISPLAY=:0`; `WAYLAND_DISPLAY=wayland-0` |
| systemd | `259 (259.5-1.fc44)` |
| Herdr | `0.8.0`; persistent server PID `3041` |
| Old Linuxbrew WezTerm | `20260117-154428-05343b38`; unlinked but retained |
| Linuxbrew tap commit | `13145a664b0ca8d000a4c183684e663307273699` |
| Active WezTerm | `20260820-083501-35680af7` at `/usr/bin/wezterm` |
| WezTerm packages | `wezterm-common` and `wezterm-gui`, release `1.fedora41` |
| Active WezTerm commit | [`35680af7`](https://github.com/wezterm/wezterm/commit/35680af7) |
| System libxkbcommon | `1.13.1-2.fc44.x86_64` |
| Herdr wrapper tests | 3 passed |
| `xkbcli compile-keymap --layout colemakp` | passed |
| `xkbcli compile-compose --locale en_US.UTF-8` | passed |
| Managed/source checksums | `herdr-shell`, `colemakp`, `evdev.xml`, and `kxkbrc` matched deployed files |
| End-to-end GUI launch | passed with no display, keymap, panic, or Compose warning |
