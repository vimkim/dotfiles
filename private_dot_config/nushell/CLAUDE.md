# Nushell Configuration Guidance

In Nushell, `source` and `use` are parser-time keywords. Any file they reference
must exist when `config.nu` is parsed. Do not guard them with runtime conditions
or reference optional files directly; select an existing file (or `null`) at
parse time instead.
