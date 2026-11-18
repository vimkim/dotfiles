# pstack model configuration. One line per role. Delete a line to fall back to the skill default.
# `inherit-parent` or `auto` as a value: the role runs on the parent chat model (omit the subagent `model` and spawn a general-purpose subagent). Alias entries in a panel list still count toward its fan-out.
# defaults: 3
# budget: large (xhigh)
# Exclude gpt-6-astra from model selection, including overrides and fallbacks.
# Codex: pass model IDs unchanged and set `reasoning_effort` separately with `fork_turns="none"`.
# Use `high` for arena runners, arena cross-judge pool, swarm workers, and interrogate reviewers.
# Use `xhigh` for the other roles below.
feature, refactoring: gpt-6.2-sol
bug-fix: gpt-6.2-sol
perf-issue: gpt-6.2-sol
hillclimb: gpt-6.2-sol
judgment and prose: gpt-6.1-sol
arena runners: gpt-6.1-sol, gpt-6.2-sol
arena cross-judge pool: gpt-6.1-sol, gpt-6.2-sol
swarm workers: gpt-6.2-sol
interrogate reviewers: gpt-6.1-sol, gpt-6.2-sol
