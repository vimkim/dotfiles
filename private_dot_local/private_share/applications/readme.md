# How to set up .desktop file

In KDE Plasma 6 Wayland (Arch Linux),

you need to make sure that the filename and the `--class` option argument matches.

Otherwise the task switcher (alt tab) would not show the proper icons.

Then, run the following command,

```sh
kbuildsycoca6 --noincremental
```

---

```text
[Containments][54][Applets][57][Configuration][General]
launchers=applications:org.wezfurlong.wezterm.desktop,applications:WezTerm1.desktop,applications:WezTerm2.desktop,applications:Alacritty.desktop,applications:kitty.desktop,preferred://browser,applications:firefox.desktop,preferred://filemanager
```

This is how it should appear in the following file:

```text
~/.config/plasma-org.kde.plasma.desktop-appletsrc
```
