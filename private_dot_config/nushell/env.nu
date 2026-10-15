# Keep env.nu free of generated shell state. Mise is exposed through its
# stable shim directory in config.nu; direnv owns project-local environment
# changes, including PATH entries.

$env.TMPDIR = ($env.HOME | path join 'tmp')
# Prefer the allocated NVMe directory when its tmp directory can be created.
if ('/mnt/nvme/data-5' | path type) == 'dir' {
    try {
        mkdir /mnt/nvme/data-5/tmp
        $env.TMPDIR = '/mnt/nvme/data-5/tmp'
    } catch { }
}
