# Nushell Configuration Guidance

In Nushell, `source` and `use` are parser-time keywords. Any file they reference
must exist when `config.nu` is parsed. Do not guard them with runtime conditions
or reference optional files directly; select an existing file (or `null`) at
parse time instead.

For an optional sourced file, use a `const` whose value is decided while parsing:

```nu
const optional_init = if ('~/.config/nushell/optional.nu' | path expand | path exists) {
  '~/.config/nushell/optional.nu'
} else {
  null
}
source $optional_init
```

Use the same pattern with `use $optional_module` for optional modules. Nushell
treats a `null` target as a no-op. This was verified with Nushell 0.114.1.

Never use `chezmoi apply --force`.

When changing a managed file, apply only that file by passing its target path
explicitly, for example: `chezmoi apply ~/.config/nushell/AGENTS.md`. Do not
run a broad apply, because unrelated managed files may have local changes.
