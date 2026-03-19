---
name: cubrid-manual
description: Search the CUBRID manual (RST docs in en/ and ko/) for SQL syntax, configuration parameters, API references, admin utilities, and any CUBRID documentation. Use when you need to look up CUBRID behavior, verify SQL semantics, or answer questions about CUBRID features.
---

# CUBRID Manual Search

Search the CUBRID official manual repository for documentation on SQL syntax, functions, configuration parameters, admin utilities, APIs, and more.

## When to Use

- When you need to verify CUBRID SQL syntax or behavior
- When answering questions about CUBRID features, parameters, or configuration
- When reviewing code and need to confirm documented semantics
- When the user asks "how does X work in CUBRID" or "what is the syntax for X"
- When any agent needs CUBRID documentation context

## Manual Location

The manual lives at `/home/vimkim/gh/cubrid-manual` with two language directories:
- `en/` — English documentation
- `ko/` — Korean documentation

All docs are reStructuredText (`.rst`) files.

## Directory Structure

- `sql/` — SQL syntax, data types, identifiers, keywords, partitions, DB admin
  - `sql/function/` — Built-in functions (string, numeric, datetime, JSON, aggregate, analytic, etc.)
  - `sql/query/` — DML statements (SELECT, INSERT, UPDATE, DELETE, MERGE, CTE, etc.)
- `admin/` — Server admin, utilities (backup, restore, compact, etc.), scripts, troubleshooting
- `api/` — Driver/API docs (JDBC, CCI, PHP, Python, Node.js, ODBC, Perl, Ruby, ADO.NET)
- `pl/` — Procedural languages (PL/CSQL, Java stored procedures, packages)
- `release_note/` — Release notes
- Top-level files: `ha.rst` (HA), `security.rst`, `shard.rst`, `csql.rst`, `env.rst`, `install.rst`, etc.

## How to Search

### Step 1: Identify the topic area

Map the user's question to the relevant directory/file based on the structure above.

### Step 2: Search with Grep

Use Grep to search across the manual RST files:

```
Grep pattern="<search_term>" path="/home/vimkim/gh/cubrid-manual/en" glob="*.rst"
```

For Korean docs:
```
Grep pattern="<search_term>" path="/home/vimkim/gh/cubrid-manual/ko" glob="*.rst"
```

### Step 3: Read relevant sections

Once you find the relevant file, read the specific section to get full context. RST files can be large, so use offset/limit to read targeted sections.

### Tips

- Search English (`en/`) by default unless the user writes in Korean or requests Korean docs
- Function docs are in `sql/function/` — e.g., `string_fn.rst`, `datetime_fn.rst`, `numeric_fn.rst`
- Configuration parameters are in `admin/admin_utils.rst` and related admin files
- For SQL syntax questions, check both `sql/` top-level files and `sql/query/` subdirectory
- Use case-insensitive search (`-i: true`) for keyword lookups
- When multiple files match, prefer the most specific one
