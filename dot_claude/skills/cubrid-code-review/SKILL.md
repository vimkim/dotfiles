---
name: cubrid-code-review
description: CUBRID database engine C/C++ PR code review skill. Performs comprehensive review covering CUBRID-specific patterns (error handling, page buffer management, locking, transactions), C/C++ correctness, concurrency safety, and database engine semantics.
---

# CUBRID C/C++ Code Review

Perform a comprehensive code review of CUBRID engine C/C++ changes. Use this when reviewing PRs or diffs in the CUBRID repository.

## When to Use

- When the user asks to review a PR (e.g., `review PR #1234`, `review this diff`)
- When the user asks for code review on CUBRID C/C++ source changes
- When the user pastes or references a diff for review

## How to Perform the Review

### Step 1: Gather Context

1. If a PR number is given, fetch the diff with `gh pr diff <number>`
2. Identify which CUBRID subsystems are touched (storage, transaction, query, parser, optimizer, broker, etc.)
3. Read surrounding code for functions being modified to understand full context
4. Check the linked JIRA ticket (CBRD-XXXXX) from the PR title/description using `/jira` for requirements context

### Step 2: Review Checklist

Evaluate the diff against ALL of the following categories. Report findings with severity:
- **[CRITICAL]** — Must fix before merge (correctness, data corruption risk, crash, security)
- **[MAJOR]** — Strongly recommended fix (resource leak, concurrency bug, logic error)
- **[MINOR]** — Improvement suggestion (style, readability, minor optimization)
- **[NIT]** — Trivial (naming, formatting, comment typo)

---

## Review Categories

### 1. CUBRID Error Handling Patterns

CUBRID uses a specific error handling idiom. Check for:

- **Return value checking**: Functions return `int error` (`NO_ERROR` = 0, negative = error). Every call that returns an error code MUST be checked.
  ```c
  // BAD - unchecked return
  some_function (thread_p, arg);

  // GOOD
  error = some_function (thread_p, arg);
  if (error != NO_ERROR)
    {
      ASSERT_ERROR ();
      goto exit;  // or return error;
    }
  ```

- **`er_set()` usage**: Errors must be set with proper severity (`ER_ERROR_SEVERITY`, `ER_WARNING_SEVERITY`, `ER_FATAL_ERROR_SEVERITY`) and `ARG_FILE_LINE` macro before returning.

- **`ASSERT_ERROR()`**: After detecting an error from a callee, use `ASSERT_ERROR()` to verify the error was actually set. This catches cases where callees forget to set errors.

- **Error propagation**: Errors must propagate up the call stack. Watch for code that silently swallows errors or resets error state.

- **Cleanup on error**: Functions using resources (pages, locks, memory) must clean up on error paths. Verify `goto exit` / `goto error` labels properly release all acquired resources.

### 2. Page Buffer Management

CUBRID's page buffer is critical infrastructure. Every `pgbuf_fix` must have a matching `pgbuf_unfix`:

- **Fix/Unfix pairing**: Every `pgbuf_fix()` call must have a corresponding `pgbuf_unfix()` on ALL code paths (success, error, early return).
- **`pgbuf_unfix_and_init()`**: Preferred over bare `pgbuf_unfix()` as it also NULLs the pointer, preventing dangling page references.
- **Latch modes**: Check that the correct latch mode is used (`PGBUF_LATCH_READ` vs `PGBUF_LATCH_WRITE`). Write latch is needed only when modifying the page.
- **Latch ordering**: Acquiring latches in inconsistent order can cause deadlocks. Verify page fix ordering follows established conventions (parent before child, left before right in B-tree).
- **Conditional vs unconditional latch**: `PGBUF_CONDITIONAL_LATCH` should be used when there's deadlock risk. Check that conditional latch failure is handled (retry or abort).
- **Page dirty marking**: After modifying a page, `pgbuf_set_dirty()` must be called before unfixing.

### 3. Lock and Concurrency Safety

- **Critical section usage**: `csect_enter` / `csect_exit` must be properly paired. Check for early returns that skip `csect_exit`.
- **Mutex pairing**: `pthread_mutex_lock` / `pthread_mutex_unlock` must be paired on all paths.
- **Lock ordering**: Acquiring multiple locks in different orders across code paths creates deadlock risk. Verify consistent ordering.
- **Shared data access**: Data accessed from multiple threads must be protected. Watch for:
  - Read-modify-write without proper synchronization
  - TOCTOU (time-of-check-time-of-use) races
  - Missing volatile or atomic operations on shared flags
- **Thread parameter**: Most server-side functions take `THREAD_ENTRY *thread_p` as first parameter. Verify it's passed correctly and not NULL where required.

### 4. Transaction and Logging Safety

- **Log before data**: WAL (Write-Ahead Logging) protocol requires log records to be written before data pages are flushed. Verify log calls precede page modifications.
- **System operation boundaries**: `log_sysop_start` / `log_sysop_end_logical_*` must be properly paired. System operations must complete or be rolled back.
- **Undo/redo correctness**: For logged operations, verify the undo and redo information is sufficient to reconstruct or reverse the operation.
- **Transaction isolation**: Check that operations respect the isolation level and don't expose uncommitted data.

### 5. Memory Management

- **Allocation/free pairing**: Every `malloc`/`calloc`/`db_private_alloc` must have a corresponding `free`/`db_private_free` on all paths.
- **NULL check after allocation**: Memory allocation can fail. Check return value before use.
- **Buffer overflows**: Check array bounds, string copy lengths (`strncpy` vs `strcpy`), format string safety.
- **Use-after-free**: Watch for pointers used after their memory is freed, especially in error cleanup paths.
- **Memory wrapper**: CUBRID uses `memory_wrapper.hpp` (must be last include). New `.c`/`.cpp` files should include it.
- **Stack buffer sizes**: Large stack allocations risk stack overflow in recursive or deeply nested call paths.

### 6. C/C++ Correctness

- **Integer overflow/underflow**: Especially in size calculations, offset arithmetic, and loop bounds.
- **Signed/unsigned comparison**: Can cause subtle bugs with negative values.
- **Null pointer dereference**: Check all pointer dereferences have prior NULL checks, especially after casts or lookups.
- **Uninitialized variables**: Variables must be initialized before use on all code paths.
- **Switch fallthrough**: Intentional fallthroughs should be commented. Unintentional ones are bugs.
- **Type casting safety**: Especially `void*` casts, narrowing conversions, and C-style casts in C++ code.
- **`assert()` with side effects**: Code inside `assert()` is removed in release builds. Never put functional code inside asserts.

### 7. CUBRID Coding Style

CUBRID follows GNU-style formatting with project-specific conventions:

- **Brace style**: Opening brace on next line, indented to the same level as the enclosing block (GNU style):
  ```c
  if (condition)
    {
      statement;
    }
  ```
- **Function spacing**: Space before parentheses in function calls: `func_name (arg1, arg2)`
- **Naming**: `snake_case` for functions and variables. Prefix with subsystem (e.g., `btree_`, `heap_`, `pgbuf_`, `lock_`, `log_`).
- **Header guards**: `#ifndef _FILENAME_H_` / `#define _FILENAME_H_` style.
- **`#ident`**: Source files include `#ident "$Id$"` after license header.
- **Include ordering**: Project headers first, then system headers. `memory_wrapper.hpp` must be the LAST include.
- **Comment style**: `/* C-style */` for `.c` files. `//` allowed in `.cpp`/`.hpp` files.
- **Mode guards**: Server-only headers use:
  ```c
  #if !defined (SERVER_MODE) && !defined (SA_MODE)
  #error Belongs to server module
  #endif
  ```

### 8. Build Mode Awareness (SERVER_MODE / SA_MODE / CS_MODE)

CUBRID compiles the same source in different modes:
- `SERVER_MODE` — multi-threaded server process
- `SA_MODE` — standalone (single-user) mode
- `CS_MODE` — client-side

- Check that `#ifdef SERVER_MODE` blocks are used correctly and don't break SA_MODE or CS_MODE compilation.
- Thread-related code should be guarded with `SERVER_MODE`.
- Functions compiled in multiple modes should handle the absence of thread_p gracefully.

### 9. Performance Considerations

- **Hot path awareness**: Changes to page buffer, lock manager, B-tree traversal, or log manager affect every query. Even small regressions matter.
- **Unnecessary copies**: Large struct copies where pointers/references suffice.
- **Lock scope minimization**: Hold locks/latches for the minimum required duration.
- **Repeated lookups**: Caching results of expensive lookups instead of re-fetching.
- **I/O in critical sections**: Never do I/O while holding critical sections or mutexes.

### 10. Test Adequacy

- **Unit tests**: Are there tests for the changed logic? Do they cover edge cases?
- **Regression risk**: Does the change affect existing test scenarios?
- **Error path testing**: Are error/failure paths tested, not just the happy path?
- **Concurrency testing**: For concurrency changes, is there a multi-threaded test?

---

## Output Format

Structure your review as:

```markdown
## PR Review: [PR title]

### Summary
[1-2 sentence summary of what the PR does and overall assessment]

### Findings

#### [CRITICAL] Title
**File:** `path/to/file.c:LINE`
**Issue:** Description of the problem
**Suggestion:** How to fix it

#### [MAJOR] Title
...

#### [MINOR] Title
...

### Positive Observations
[Note any well-done aspects: good error handling, clear logic, good test coverage]

### Questions for Author
[Any clarifying questions about design decisions or intent]
```

### Tools

- **clangd LSP tools**: You can freely use clangd-related LSP tools during review. These are especially useful for:
  - `lsp_document_symbols` — get an overview of all functions/types in a file
  - `lsp_goto_definition` — jump to the definition of a function or type to understand its contract
  - `lsp_find_references` — find all callers/usages to assess impact of a change
  - `lsp_hover` — get type information and documentation for symbols
  - `lsp_diagnostics` — check for compiler warnings/errors detected by clangd

### Tips
- Read the JIRA ticket for full requirements context before reviewing
- Check git history of modified functions for recent related changes
- When in doubt about CUBRID conventions, look at surrounding code in the same file
- Pay extra attention to subsystem boundaries (e.g., storage calling transaction APIs)
- For large PRs, prioritize reviewing the core logic changes over mechanical/boilerplate changes
