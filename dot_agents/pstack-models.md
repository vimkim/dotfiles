# pstack model configuration. One line per role. Delete a line to fall back to the skill default.
# `inherit-parent` or `auto` as a value: the role runs on the parent chat model (omit the subagent `model`). Alias entries in a panel list still count toward its fan-out.
# budget: large (xhigh)
# Codex: for explicit model choices, pass the model ID unchanged and the budget effort as `reasoning_effort`, with `fork_turns="none"`.
feature, refactoring: gpt-6.1-terra
bug-fix: gpt-6.1-terra
perf-issue: gpt-6.1-terra
hillclimb: gpt-6.1-terra
judgment and prose: gpt-6.1-sol
hardest tasks: gpt-6.1-sol
how explorer: gpt-6.1-terra
how explainer: gpt-6.1-sol
why investigators: gpt-6.1-terra
why synthesizer: gpt-6.1-sol
reflect tooling: gpt-6.1-terra
reflect judgment, divergent, synthesizer: gpt-6.1-sol
arena runners: gpt-6.1-sol, gpt-6.1-terra
arena cross-judge pool: gpt-6.1-sol, gpt-6.1-terra
swarm workers: gpt-6.1-terra
architect runners: gpt-6.1-sol, gpt-6.1-terra
interrogate reviewers: gpt-6.1-sol, gpt-6.1-terra
