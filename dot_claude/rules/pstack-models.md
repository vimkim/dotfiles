# pstack model configuration. One line per role. Delete a line to fall back to the skill default.
# `inherit-parent` or `auto` as a value: the role runs on the parent chat model (omit the subagent `model` and spawn a general-purpose subagent). Alias entries in a panel list still count toward its fan-out.
# Claude Code: pass the value as the Agent `model` alias and the budget effort as the Agent `effort`.
# defaults: 3
# budget: large (xhigh)
feature, refactoring: sonnet
bug-fix: sonnet
perf-issue: sonnet
hillclimb: sonnet
judgment and prose: opus
arena runners: opus, sonnet
arena cross-judge pool: opus, sonnet
swarm workers: sonnet
interrogate reviewers: opus, sonnet
