# Global Agent Guidance

## Important local CUBRID context

- `/home/vimkim/gh/my-cubrid-docs` is an important local knowledge base for CUBRID design notes, architecture context, and project documentation. Check it before relying on web search for CUBRID-specific context.
- `/home/vimkim/gh/my-cubrid-jira` is an important local knowledge base for CUBRID JIRA issue drafts, issue reports, and planning notes. Check it when working with CBRD tickets, PR context, or issue writeups.
- `just` / `justfile` commands in local CUBRID worktrees are personal convenience tooling only. Do not present them as CUBRID organization workflow, reviewer instructions, PR verification commands, or public project documentation. For CUBRID-org-facing text, use standard build/test concepts such as CMake, ctest, or the project-provided scripts instead.
- For your own local rebuilds while fixing CUBRID code, run `just build` and `just build-test` instead of invoking CMake directly (direct CMake often fails); these are ccache-backed and finish almost instantly.

## CUBRID source indentation

- When working inside a CUBRID source repository, preserve the existing indentation exactly. Do not introduce meaningless indentation-only changes. If indentation changes without a semantic reason, report it because it may be a GNU indent bug.
- CUBRID compiles most source files as C++, except for a few parser- and flex/bison-related files. However, legacy `.c` and `.h` files are formatted with GNU indent, so any C++-specific syntax in those files must be wrapped exactly as follows:

```c
/* *INDENT-OFF* */
C++ syntax code
/* *INDENT-ON* */
```

## Clarification policy

- If my request is ambiguous in any way, ask a concise clarifying question before acting instead of assuming defaults.

## Task tracking

- For substantive implementation, debugging, review, or research tasks, create a concise active goal from my request before doing long-running work. Keep the goal updated when the task meaning changes, so I can return later and quickly see what the agent was doing.
