# CUBRID C/C++ Review Checklist

Detailed review categories for CUBRID database engine code. Evaluate each modified hunk against all applicable categories.

## Severity Levels

- **[CRITICAL]** — Must fix before merge (correctness, data corruption, crash, security, LSP errors)
- **[MAJOR]** — Strongly recommended fix (resource leak, concurrency bug, logic error, LSP warnings)
- **[MINOR]** — Improvement suggestion (style, readability, optimization)
- **[NIT]** — Trivial (naming, formatting, comment typo)

---

## 1. Error Handling Patterns

CUBRID uses a specific error idiom. Check for:

- **Return value checking**: Functions return `int error` (`NO_ERROR` = 0, negative = error). Every call returning an error code MUST be checked.
  ```c
  // BAD - unchecked return
  some_function (thread_p, arg);

  // GOOD
  error = some_function (thread_p, arg);
  if (error != NO_ERROR)
    {
      ASSERT_ERROR ();
      goto exit;
    }
  ```
- **`er_set()` usage**: Errors must use proper severity (`ER_ERROR_SEVERITY`, `ER_WARNING_SEVERITY`, `ER_FATAL_ERROR_SEVERITY`) and `ARG_FILE_LINE` macro.
- **`ASSERT_ERROR()`**: After detecting an error from a callee, use `ASSERT_ERROR()` to verify the error was actually set.
- **Error propagation**: Errors must propagate up the call stack. Watch for silently swallowed errors.
- **Cleanup on error**: Functions using resources (pages, locks, memory) must clean up on error paths. Verify `goto exit`/`goto error` labels release all acquired resources.

## 2. Page Buffer Management

Every `pgbuf_fix` must have a matching `pgbuf_unfix`:

- **Fix/Unfix pairing**: Every `pgbuf_fix()` must have `pgbuf_unfix()` on ALL code paths (success, error, early return).
- **`pgbuf_unfix_and_init()`**: Preferred over bare `pgbuf_unfix()` — also NULLs the pointer.
- **Latch modes**: `PGBUF_LATCH_READ` vs `PGBUF_LATCH_WRITE`. Write latch only when modifying.
- **Latch ordering**: Inconsistent order → deadlock. Verify conventions (parent before child, left before right in B-tree).
- **Conditional latch**: `PGBUF_CONDITIONAL_LATCH` when deadlock risk exists. Check failure handling.
- **Page dirty marking**: `pgbuf_set_dirty()` must be called before unfixing a modified page.

## 3. Lock and Concurrency Safety

- **Critical section pairing**: `csect_enter`/`csect_exit` must be paired. Check early returns that skip exit.
- **Mutex pairing**: `pthread_mutex_lock`/`pthread_mutex_unlock` paired on all paths.
- **Lock ordering**: Multiple locks in different orders → deadlock risk.
- **Shared data access**: Must be protected. Watch for:
  - Read-modify-write without synchronization
  - TOCTOU races
  - Missing volatile/atomic on shared flags
- **Thread parameter**: `THREAD_ENTRY *thread_p` must be passed correctly and not NULL where required.

## 4. Transaction and Logging Safety

- **WAL protocol**: Log records written before data pages flushed. Verify log calls precede page modifications.
- **System operation boundaries**: `log_sysop_start`/`log_sysop_end_logical_*` must be paired.
- **Undo/redo correctness**: Verify information is sufficient to reconstruct or reverse the operation.
- **Transaction isolation**: Operations must respect isolation level, not expose uncommitted data.

## 5. Memory Management

- **Allocation/free pairing**: `malloc`/`calloc`/`db_private_alloc` must have corresponding free on all paths.
- **NULL check after allocation**: Memory allocation can fail.
- **Buffer overflows**: Array bounds, string copy lengths (`strncpy` vs `strcpy`), format string safety.
- **Use-after-free**: Pointers used after free, especially in error cleanup paths.
- **Memory wrapper**: `memory_wrapper.hpp` must be last include in `.c`/`.cpp` files.
- **Stack buffer sizes**: Large stack allocations risk overflow in recursive/deep call paths.

## 6. C/C++ Correctness

- **Integer overflow/underflow**: Size calculations, offset arithmetic, loop bounds.
- **Signed/unsigned comparison**: Subtle bugs with negative values.
- **Null pointer dereference**: Check dereferences have prior NULL checks, especially after casts/lookups.
- **Uninitialized variables**: Must be initialized before use on all code paths.
- **Switch fallthrough**: Intentional ones must be commented.
- **Type casting safety**: `void*` casts, narrowing conversions, C-style casts in C++ code.
- **`assert()` with side effects**: Code inside `assert()` removed in release builds.

## 7. Coding Style

GNU-style formatting with CUBRID conventions:

- **Brace style**: Opening brace on next line, indented to enclosing block level (GNU style)
- **Function spacing**: Space before parentheses: `func_name (arg1, arg2)`
- **Naming**: `snake_case`, subsystem prefix (`btree_`, `heap_`, `pgbuf_`, `lock_`, `log_`)
- **Header guards**: `#ifndef _FILENAME_H_` / `#define _FILENAME_H_`
- **Include ordering**: Project headers first, then system. `memory_wrapper.hpp` last.
- **Comment style**: `/* C-style */` in `.c`, `//` allowed in `.cpp`/`.hpp`
- **Mode guards** for server-only headers:
  ```c
  #if !defined (SERVER_MODE) && !defined (SA_MODE)
  #error Belongs to server module
  #endif
  ```

## 8. Build Mode Awareness

CUBRID compiles same source in multiple modes: `SERVER_MODE` (multi-threaded server), `SA_MODE` (standalone), `CS_MODE` (client).

- `#ifdef SERVER_MODE` blocks must not break SA_MODE or CS_MODE compilation.
- Thread-related code guarded with `SERVER_MODE`.
- Functions in multiple modes must handle absence of `thread_p`.

## 9. Performance

- **Hot path awareness**: Page buffer, lock manager, B-tree, log manager changes affect every query.
- **Unnecessary copies**: Large struct copies where pointers/references suffice.
- **Lock scope minimization**: Hold locks/latches for minimum duration.
- **Repeated lookups**: Cache results of expensive lookups.
- **I/O in critical sections**: Never do I/O while holding critical sections or mutexes.

## 10. Test Adequacy

- **Unit tests**: Tests for changed logic? Edge cases covered?
- **Regression risk**: Does the change affect existing test scenarios?
- **Error path testing**: Error/failure paths tested, not just happy path?
- **Concurrency testing**: Multi-threaded test for concurrency changes?
