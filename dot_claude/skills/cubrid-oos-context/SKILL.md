---
name: cubrid-oos-context
description: Load CUBRID OOS (Out-of-row Overflow Storage) project context from the local knowledge vault and JIRA. Use this skill whenever OOS is mentioned, when working on the feat/oos branch, when touching oos_file.cpp or OOS-related heap_file.c code, when CBRD-26517/26458/26516 or other OOS JIRA tickets come up, or when you need to understand the OOS architecture, record format, CRUD flows, or MVCC integration. Also trigger when you see OOS-related identifiers like OR_MVCC_FLAG_HAS_OOS, OR_VAR_BIT_OOS, FILE_OOS, oos_insert, oos_read, oos_delete, or heap_record_replace_oos_oids.
---

# CUBRID OOS Context

This skill loads context about the **OOS (Out-of-row Overflow Storage)** project — a CUBRID feature that separates large variable-length columns from heap records into dedicated OOS files to reduce unnecessary disk I/O.

$ARGUMENTS

## Step 1: Load core context from the vault

Read the two key files from the local Obsidian vault:

```
/home/vimkim/gh/cubrid-oos-vault/content/CLAUDE.md
/home/vimkim/gh/cubrid-oos-vault/content/index.md
```

The `CLAUDE.md` file contains the authoritative summary: trigger conditions, record format, CRUD flows, key source files, recovery invariants, known bugs, and milestones. The `index.md` is the vault's table of contents with links to deeper docs.

These two files together give you enough context for most OOS-related questions. Read them both before answering.

## Step 2: Look up JIRA issues (if needed)

If a specific CBRD ticket is mentioned, or if you need current status on an OOS issue, use `cubrid-jira-search`:

```bash
cubrid-jira-search CBRD-XXXXX
```

Key OOS JIRA tickets:
- **CBRD-26517** — Main OOS tracking issue
- **CBRD-26458** — unloaddb `heap_next` performance regression
- **CBRD-26516** — UPDATE redundant `oos_read` calls
- **CBRD-26637** — OOS error handling refactor (er_set + ASSERT_ERROR)

## Step 3: Semantic search (if needed)

When you need context beyond the core files, use `cubrid-oos-search` to find relevant chunks across the entire vault (82 docs, 4177 chunks). This is faster and more targeted than reading individual files.

```bash
# Search for specific topics
cubrid-oos-search search "vacuum OOS cleanup" -k 5

# Adjust result count
cubrid-oos-search search "page buffer fix latch" -k 3
```

The tool runs locally with embedded vectors (no API calls). Re-index after vault changes with `cubrid-oos-search index`.

## Step 4: Dive deeper (if needed)

The vault at `/home/vimkim/gh/cubrid-oos-vault/content/` contains additional documents for deep dives:

| Document | Path | Content |
|----------|------|---------|
| OOS Presentation | `OOS-Presentation.md` | Architecture slides (Marp), design rationale, CRUD diagrams |
| OOS Test Scenarios | `OOS-Test-Scenarios.md` | ACID, crash recovery, MVCC, replication test cases |
| OOS Schedule | `oos-schedule.md` | M2 milestone timeline, task assignments |
| OOS TODO | `oos-todo.md` | Known bugs, optimization ideas, design discussions |
| OOS Delete Analysis | `oos-delete-analysis.md` | DELETE operation analysis |
| Heap Bestspace | `reference/storage/heap_bestspace_algorithm.md` | How CUBRID picks heap pages for insertion |
| Heap File | `reference/storage/heap_file.md` | heap_file.c analysis |
| Page Buffer | `reference/storage/page_buffer.md` | page_buffer.c analysis |
| Storage Index | `reference/storage/INDEX.md` | Index of all storage layer reference docs |

Only read these if the core context and semantic search aren't sufficient for the question at hand.

## Quick Reference

| Concept | Detail |
|---------|--------|
| OOS trigger | record > `DB_PAGESIZE/8` (2KB on 16KB pages) AND column > 512B |
| OOS file type | `FILE_OOS`, one per heap file (1:1 mapping) |
| OOS pointer | 8-byte OOS OID (volid, pageid, slotid) in variable area |
| MVCC flags | `OR_MVCC_FLAG_HAS_OOS` (bit 3), `OR_VAR_BIT_OOS` (bit 0) |
| Key sources | `heap_file.c`, `oos_file.cpp`, `object_representation.h` |
| Branch | `feat/oos` |
| Current milestone | M2 (3/10-4/17): bestspace, compaction, vacuum, drop table |
