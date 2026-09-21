# Global Agent Guideline

## Daily/weekly schedule

- My daily and weekly work plans live in `/home/vimkim/temp/todays-schedule` (control sheets + raw prompts) and the `work-tracker` ledger. When I ask what to do today/next, what I planned, or hand over a plan — from any directory — follow the `daily-schedule` skill.

## Important local CUBRID context

- `/home/vimkim/my-cubrid` is an important local personal directory containing many helpful utilities and scripts for developing CUBRID.
- `/home/vimkim/gh/my-cubrid-docs` is an important local knowledge base for CUBRID design notes, architecture context, and project documentation. Check it before relying on web search for CUBRID-specific context.
- `/home/vimkim/gh/my-cubrid-jira` is an important local knowledge base for CUBRID JIRA issue drafts, issue reports, and planning notes. Check it when working with CBRD tickets, PR context, or issue writeups.

### cubrid source repo

- /home/vimkim/gh/cb is a directory containing worktrees for https://github.com/CUBRID/cubrid repo.
- /home/vimkim/gh/cb/develop is for example, a worktree with develop branch.
- My major works are done in here. It has origin remote (github.com/CUBRID/cubrid) and vk remote (github.com/vimkim/cubrid). Most of my works are done in vk, unless the HEAD branch pattern matches 'feature/*'.
- /home/vimkim/my-cubrid/./stow/cubrid/justfile is usually stowed into the worktree and supports various helpful commands like `just build`.
- `just worktree xxxx` will create a new worktree in /home/vimkim/gh/cb/xxxx.
- The canonical naming for worktree is CBRD-NNNNN-descriptions. This is being checked inside `just worktree xxxx`.

## CUBRID CI, test cases and Regression tests

In order to merge a PR targeting 'develop' branch in CUBRID, one must pass CUBRID CI in GitHub PR.
It contains many CI checks like build, codestyle, etc. They are trivial. The difficult part is to pass tests.

There are 3 major categories for tests.
- test_medium: finishes within 10 min
- test_sql: finishes within 30 min
- test_shell: might take about 1 hour

### cubrid-testcases

- /home/vimkim/gh/cubrid-testcases is a directory containing worktrees for https://github.com/CUBRID/cubrid-testcases repo.
- /home/vimkim/gh/cubrid-testcases/develop is for example, path to a worktree with develop branch.
- TCs for test_medium and test_sql are located there.
- When editing TCs for a cubrid PR, create worktree with the same branch name there. Follow the canonical cubrid repo naming convention for consistency.


### cubrid-testcases-private-ex

- /home/vimkim/gh/cubrid-testcases-private-ex is a directory containing worktrees for https://github.com/CUBRID/cubrid-testcases-private-ex repo.
- /home/vimkim/gh/cubrid-testcases/develop is for example, a worktree with develop branch.
- TCs for test_shell is located there.
- When editing TCs for a cubrid PR, create worktree with the same branch name there. Follow the canonical cubrid repo naming convention for consistency.
- This repo is private but I have access to it.

### CUBRID manual tests and regression tests

- CUBRID QA team separately runs daily regression tests on 'develop' branch.
- This contains not only the 3 basic CI tests (test_medium, test_sql, test_shell) but also other tests like replication, isolation, etc.
- TCs for these tests are also located inside cubrid-testcases and cubrid-testcases-prviate-ex, etc.

## Personal tool: Just

- `just` / `justfile` commands in local CUBRID worktrees are personal convenience tooling only. Do not present them as CUBRID organization workflow, reviewer instructions, PR verification commands, or public project documentation. For CUBRID-org-facing text, use standard build/test concepts such as CMake, ctest, or the project-provided scripts instead.
- /home/vimkim/my-cubrid/./stow/cubrid/justfile is the main helper for active CUBRID development.
- /home/vimkim/my-cubrid/cubrid-justfiles/justfile is a supplementary helper.

## CUBRID development

### CUBRID build

- For your own local rebuilds while fixing CUBRID code, run `just build` and `just build-test` instead of invoking CMake directly (direct CMake often fails); these are ccache-backed and finish almost instantly.

### CUBRID source indentation

- When working inside a CUBRID source repository, preserve the existing indentation exactly. Do not introduce meaningless indentation-only changes. If indentation changes without a semantic reason, report it because it may be a GNU indent bug.
- CUBRID compiles most source files as C++, except for a few parser- and flex/bison-related files. However, legacy `.c` and `.h` files are formatted with GNU indent, so any C++-specific syntax in those files must be wrapped exactly as follows:

```c
/* *INDENT-OFF* */
C++ syntax code
/* *INDENT-ON* */
```

### CUBRID error convention

- The cubrid source repo AGENTS.md says: do not use cpp try catch. This is stale.
When using cpp STL data structures like std::vector, there is no other way to deal with exceptions other than try catch -> immediate conversion to C-style, CUBRID conventional error handling. This is permitted.
- When writing cpp STL, prefer using a new file with cpp extension.
- When you must use cpp STL in pre-existing file with c extension, convert the cpp exceptions into c-style error immediately at the call site.

## Clarification policy

- If my request is ambiguous, interview me relentlessly. Do not assume.

## Task tracking

- Use worktracker CLI for tracking my works.
