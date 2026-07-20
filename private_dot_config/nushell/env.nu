# env.nu runs before config.nu is parsed, so files generated here can be
# `use`d in config.nu without a chicken-and-egg parse error on fresh machines.

# mise activation script, consumed by `use` at the end of config.nu.
let mise_path = $nu.default-config-dir | path join mise.nu
if (which mise | is-not-empty) {
    ^mise activate nu | save $mise_path --force
} else if not ($mise_path | path exists) {
    # Keep config.nu parseable even when mise is not installed.
    "" | save $mise_path
}
