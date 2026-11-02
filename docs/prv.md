# prv

Open a GitHub pull request as a red/green diff with full file context, in the
terminal. GitHub's diff view and tools that read `gh pr diff` show only a few
lines around each change. prv fetches the pull request into the local clone
and diffs it there, so the viewer can show whole files. Requires Python 3.9 or
newer, Git, and `gh`. No Python packages are needed.

```sh
prv 'https://github.com/CUBRID/cubrid/pull/8299'
prv 'https://github.com/CUBRID/cubrid/pull/8299/changes#diff-86bbecbb...'   # opens that file first
prv 'https://github.com/CUBRID/cubrid/pull/8299' nav     # diffnav: file tree + delta
prv 'https://github.com/CUBRID/cubrid/pull/8299' delta   # plain delta pager
PRV_CONTEXT=-W prv '<url>' nav                           # whole changed functions, not whole files
prv -n '<url>'                                           # print the viewer command only
prv --prune                                              # delete refs/prv/*
```

## Modes

| Mode | Viewer | Context |
| --- | --- | --- |
| `nvim` (default) | diffview.nvim, side by side, every PR file | whole files |
| `nav` | diffnav: file tree and delta | `PRV_CONTEXT`, default `-U100000` |
| `delta` | delta pager | `PRV_CONTEXT`, default `-U100000` |

In `nvim` mode, Vim folds unchanged regions. Press `zR` to open every fold. The
diffview buffers are Git objects, so the language server does not attach. To
use go-to-definition, check the PR out in a worktree and run
`:DiffviewOpen <merge-base>` there.

## Behavior

Run prv inside a local clone of the pull request's repository. Any linked
worktree works. prv:

1. Finds the remote whose URL points at the repository in the URL. HTTPS, SSH,
   and `git@github.com:` remotes match, ignoring case.
2. Reads the base branch with `gh pr view`.
3. Fetches `refs/pull/<n>/head` and the base branch into
   `refs/prv/<n>/head` and `refs/prv/<n>/base` through that remote. Pull
   requests from forks work, because GitHub publishes their heads in the base
   repository. Branches, remote-tracking branches, and the working tree do not
   change.
4. Diffs from the merge base of the two refs, as GitHub does.

A URL fragment `#diff-<sha256>` names a file: GitHub uses the SHA-256 of the
file path. A line suffix such as `R12` or `L3-R5` is accepted and ignored. If
no changed file matches, prv shows every file and prints a notice on stderr.

`-n` still fetches, because the command contains the merge base. Exit status
is 2 for input errors (not a pull request URL, no matching remote, not in a Git
repository) and 1 for failures of `git` or `gh`.

Chezmoi manages the executable source at `private_dot_local/bin/executable_prv`
and deploys it to `~/.local/bin/prv`. The login profile and the zsh, bash, and
nushell configurations put that directory on PATH.

Run the focused checks with the system Python 3.9 and the default Python:

```sh
/usr/bin/python3 -m unittest discover -s tests -p test_prv.py -v
python3 -m unittest discover -s tests -p test_prv.py -v
```
