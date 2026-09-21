# Global Agent Guidance

## Working preferences

- Clarify only ambiguities whose answers could materially change the outcome, scope, or risk. Continue asking until those decisions are resolved; handle routine, reversible details with explicit assumptions.
- Track work with `work-tracker` when it is expected to take at least 30 minutes, cross sessions, use parallel agents, or wait on an external queue. Leave short, same-turn work unregistered.

## Daily and weekly schedule

- When asked what to do today or next, what was planned, or to track a daily or weekly plan, use the `daily-schedule` skill. Its sources of truth are `/home/vimkim/temp/todays-schedule` and the `work-tracker` ledger.

## CUBRID context

- For CUBRID work involving worktrees, remotes, CI or regression suites, or testcase repositories, read `/home/vimkim/my-cubrid/CUBRID.md` before acting.
- Before web research for CUBRID-specific design or architecture context, search `/home/vimkim/gh/my-cubrid-docs`.
- For CBRD tickets, PR context, or issue writeups, search `/home/vimkim/gh/my-cubrid-jira`.

## CUBRID local development

- Use the personal `just` recipes for local development, especially `just build` and `just build-test`. In CUBRID organization-facing documentation, PR text, reviewer instructions, and verification steps, express the workflow with project-provided scripts, CMake, or ctest rather than personal recipes.
- Preserve existing indentation exactly and keep formatting changes semantically necessary. Report unexplained indentation-only changes as possible GNU indent issues.
- Most CUBRID `.c` sources compile as C++, while legacy `.c` and `.h` files are formatted with GNU indent. Wrap C++-specific syntax added to those legacy files exactly as follows so GNU indent preserves it:

```c
/* *INDENT-OFF* */
C++ syntax code
/* *INDENT-ON* */
```

- The repository-local blanket ban on C++ exceptions is stale for throwing STL operations. Prefer new `.cpp` files for new STL code; catch exceptions at the call site and immediately translate them into CUBRID's C-style error handling, including when STL must be used in an existing `.c` file.
