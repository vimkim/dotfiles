---
trigger: always_on
description: Antigravity pstack per-role model choices (overrides ~/.agents/pstack-models.md and skill defaults)
---
# pstack model configuration for Antigravity (agy).
# In Antigravity, use this file instead of ~/.agents/pstack-models.md (which is reserved for Codex) and instead of pstack skill defaults.
# Do not overwrite ~/.agents/pstack-models.md from Antigravity; edit this rule file's chezmoi source instead.
# `inherit-parent` or `auto`: run on the parent session model (e.g., Orchestrator (Neon)); omit `model` in `swarm`, or pass `Model: "inherit"` in `invoke_subagent`.
# Tool mapping:
# - `swarm` tool: accepts exact `agy models` slugs below. Use `swarm` for cross-vendor panels (`arena`, `interrogate`) so Gemini and Claude arms run on distinct models.
# - `invoke_subagent` tool (only supports `inherit`, `flash_lite`, `flash`, `pro`): map `inherit-parent` -> `inherit`, `gemini-4-hydrogen-high` -> `flash`, and `gemini-4-neon-high` -> `pro`.
# defaults: 3
# budget: medium (high)
feature, refactoring: inherit-parent
bug-fix: inherit-parent
perf-issue: inherit-parent
hillclimb: inherit-parent
judgment and prose: inherit-parent
arena runners: gemini-4-neon-high, claude-opus-5-5-high
arena cross-judge pool: claude-opus-5-5-high, gemini-4-neon-high
swarm workers: gemini-4-hydrogen-high
interrogate reviewers: gemini-4-neon-high, claude-opus-5-5-high
