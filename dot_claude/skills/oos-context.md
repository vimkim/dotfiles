# OOS Context Skill

Fetch the latest OOS (Out-of-row Overflow Storage) project context from the knowledge base.

When the user mentions "OOS", "OOS project", or asks about OOS-related work, use this skill to fetch up-to-date context.

## Steps

1. Fetch the OOS knowledge base from `https://vimkim.dev/cubrid-oos-vault/CLAUDE` using WebFetch
2. Present the relevant context to the user
3. If the user has a specific question, use the fetched context along with codebase search to answer it
