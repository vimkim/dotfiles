# Domain Docs

This repository has one domain context:

- `GLOSSARY.md` at the repository root contains canonical vocabulary.
- `docs/adr/` contains architectural decisions when needed.

Before exploring the codebase, read the glossary and any ADRs relevant to the
area being changed. Use glossary terms in issue titles, proposals, hypotheses,
and test names.

If a glossary or ADR directory is absent, proceed silently. The
`domain-modeling` skill creates vocabulary and decisions lazily; setup does
not create placeholder ADRs.

When a necessary domain term is missing or ambiguous, use `domain-modeling`
to sharpen it. Keep implementation details in design documents rather than
glossary definitions.

Surface conflicts with existing ADRs before proposing a deviation.
