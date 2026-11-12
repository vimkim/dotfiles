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

# Claude Code cannot run its Bash tool in nu, so it auto-picks zsh before bash.
# Pin bash for Claude Code only; SHELL and the login shell stay nu.
$env.CLAUDE_CODE_SHELL = (
    ['/home/linuxbrew/.linuxbrew/bin/bash' '/bin/bash']
    | where {|p| $p | path exists }
    | first
)

# CUBRID engine checkout that cubrid-tcr check reads for fix commits.
$env.TCR_ENGINE_REPO = ($env.HOME | path join gh/cb/develop)
