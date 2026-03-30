---
name: create-testcases
description: Create CUBRID test cases (unit/SQL/shell) for a given feature or bug fix. Use when the user asks to create tests, write test cases, or mentions testing a CBRD ticket.
argument-hint: [feature-description or CBRD-XXXXX]
disable-model-invocation: true
---

Create CUBRID test cases for a given feature or bug fix.

Given a description of the feature/fix to test (and optionally a JIRA ticket like CBRD-XXXXX), create all three types of test cases:

1. **Unit tests** (Google Test, C++)
2. **SQL tests** (csql-based)
3. **Shell tests** (bash-based)

$ARGUMENTS

---

## OOS Test Case Guidelines

When creating test cases for **OOS (Out of Space)** scenarios:
- **Use BIT VARYING (VARBIT)** data type instead of string types (VARCHAR, CHAR, etc.) for data that needs predictable on-disk size.
- **Reason**: CUBRID compresses strings, making actual disk usage unpredictable unless the server is stopped and compression is disabled. VARBIT data is not compressed, so its size is predictable — critical for OOS tests that need to fill storage to specific thresholds.

## Step 1: Understand what to test

- If a CBRD ticket is mentioned, use `/jira` to fetch context first.
- Read the relevant source code to understand the feature/fix being tested.
- Identify the key behaviors, edge cases, and error conditions to cover.

## Step 2: Create Unit Tests

**Reference**: `unit_tests/oos/` in the current project directory for patterns.

**Location**: Create in `unit_tests/<feature_name>/` under the project root.

**Conventions**:
- File naming: `test_<feature>.cpp`
- Use Google Test framework (`GTest::gtest`)
- Shared infrastructure goes in `test_<feature>_common.hpp`
- Each test file has its own `main()`:
  ```cpp
  int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    ::testing::AddGlobalTestEnvironment(new ServerEnv());
    ::testing::GTEST_FLAG(break_on_failure) = true;
    return RUN_ALL_TESTS();
  }
  ```
- Link against `${EP_LIBS} cubridsa GTest::gtest` with `SA_MODE`
- Use RAII patterns (unique_ptr with custom deleters) for page/record cleanup
- Use bridge functions to access static internals when needed
- Use `ASSERT_*` macros with descriptive messages
- Create a `CMakeLists.txt` that globs `test_*.cpp` and creates one executable per file

**Files to create**:
- `unit_tests/<feature>/CMakeLists.txt`
- `unit_tests/<feature>/test_<feature>.cpp`
- Optionally: `test_<feature>_common.hpp` for shared utilities

## Step 3: Create SQL Tests

**Reference**: `~/gh/tc/cubrid-testcases/sql/` for patterns.

**Location**: Create under `~/gh/tc/cubrid-testcases/sql/_36_guava/` (or appropriate category).

**Conventions**:
- Directory structure: `<test_dir>/cases/<name>.sql` and `<test_dir>/answers/<name>.answer`
- Test naming: use JIRA ticket ID if available (e.g., `cbrd_26609.sql`), otherwise descriptive name
- SQL file contains: setup DDL, test DML/queries, cleanup (DROP statements)
- Use `autocommit on;` at the top if needed
- Answer file contains expected output with `===` separators between statements
- If the answer file cannot be determined ahead of time, create the `.sql` file and add a comment explaining the user should run it and capture the output as the `.answer` file

**Files to create**:
- `~/gh/tc/cubrid-testcases/sql/<category>/<test_name>/cases/<name>.sql`
- `~/gh/tc/cubrid-testcases/sql/<category>/<test_name>/answers/<name>.answer` (if deterministic)

## Step 4: Create Shell Tests

**Reference**: `~/cubrid-testcases-private-ex/shell/` for patterns.

**Location**: Create under `~/cubrid-testcases-private-ex/shell/` in the appropriate category.

**Conventions**:
- Directory structure: `<category>/<test_name>/cases/<test_name>.sh`
- Test script sources `$init_path/init.sh` for helper functions
- Standard flow:
  ```bash
  #!/bin/bash
  . $init_path/init.sh
  init test

  # Setup
  cubrid_createdb testdb
  cubrid server start testdb

  # Test operations
  csql -c "SQL" testdb
  # ... verify results ...

  # Cleanup
  cubrid server stop testdb
  cubrid deletedb testdb
  finish
  ```
- Use `write_ok` / `write_nok` to record pass/fail
- Use `test_exec_sql` and `test_exec_command` helpers
- Result format: `<test_name>-N : OK` or `<test_name>-N : NOK`
- Create `.result` file with expected pass/fail lines

**Files to create**:
- `~/cubrid-testcases-private-ex/shell/<category>/<test_name>/cases/<test_name>.sh`
- `~/cubrid-testcases-private-ex/shell/<category>/<test_name>/cases/<test_name>.result`

## Step 5: Summary

After creating all test files, present a summary table:

| Type | Path | Description |
|------|------|-------------|
| Unit | `unit_tests/...` | ... |
| SQL  | `~/gh/tc/...` | ... |
| Shell | `~/cubrid-testcases-private-ex/...` | ... |

Ask the user if they want to adjust any of the test cases.
