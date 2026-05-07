---
name: grill-and-revise
description: "Iteratively improve a document by looping a writer subagent against a relentless reviewer subagent until the reviewer explicitly approves or a round cap is hit. Use whenever the user wants high-quality long-form writing (reports, design docs, JIRA issues, blog posts, technical analysis, RFCs, postmortems) and is willing to trade time for rigor — even when they don't say 'loop' or 'review', trigger this when they ask for a *thorough*, *bulletproof*, *peer-reviewed*, *grilled*, *stress-tested*, or *adversarially-reviewed* document, or when they explicitly ask to 'have another agent review' their writing, or say things like 'don't ship until it's solid'."
---

# Grill-and-Revise

A two-agent loop for producing rigorous documents. One subagent writes; another grills it relentlessly. The writer revises until the reviewer is satisfied — or a round cap stops the loop and hands control back to the human.

## Why this exists

Single-pass writing tends toward hand-wavy, filler-heavy prose. A *separate* reviewer — one with no investment in defending the draft — catches what the writer missed; looping forces real iteration instead of cosmetic edits, and the explicit verdict keeps the loop honest. Self-review collapses into self-justification, which is why this skill always uses two distinct agents.

## When to use

Long-form writing where quality matters more than speed and the user will spend tokens on iteration. Skip short messages, code comments, or anything you could write in two sentences.

## Inputs to gather before launching

Ask the user (briefly, all at once) if these aren't already clear from context:

1. **Topic & purpose** — what is the document, and who is the audience?
2. **Output path** — where should the draft live? Default: `./drafts/<slug>.md` in the current working directory.
3. **Source material** — any reference files, transcripts, code, data, links the writer should ground in? Without this, the writer will fabricate confident-sounding filler and the reviewer will (correctly) tear it apart forever.
4. **Review angle** — what should the reviewer prioritize? Examples: technical accuracy, persuasiveness, clarity for non-experts, specific load-bearing claims to challenge. Default: general rigor — evidence, structure, clarity, no hand-waving.
5. **Round cap** — defaults to 5. The user can override.

Confirm before launching. The loop runs subagents and burns tokens; don't fire it speculatively from an ambiguous request.

## The loop

Track this state across rounds:

- `draft_path` — file the writer writes to and the reviewer reads.
- `round` — starts at 1, increments each cycle.
- `max_rounds` — default 5.
- `last_critique` — the reviewer's most recent feedback (empty on round 1).

Run rounds in this order:

### Step 1 — Writer pass

Spawn a writer subagent. Use `subagent_type=executor` with `model=opus` for technically dense or high-stakes topics, `sonnet` otherwise. Give the writer:

- The topic, purpose, audience, and any source material (paths or inline content).
- The exact `draft_path`. Tell it: "Read the existing draft at this path if present; otherwise create the file. Save the revised draft to this exact path."
- A required TL;DR: "Start the document with a `## TL;DR` section containing a 3-5 line plain-language summary of what the document says and why it matters. Write it for a human skimming in 10 seconds — no jargon dump, no bullet salad."
- On rounds ≥ 2, include the reviewer's `last_critique` verbatim and instruct: "Address every numbered point. If you disagree with a point, revise the document so the reviewer's concern no longer applies — do not argue back inside the document. Don't add 'reviewer asked for X' notes, change markers, or meta-commentary; the output is the document, not a changelog."
- A reminder that the writer should not explain its changes to *you* (the orchestrator) at length. Tell it: "Return only the literal string `OK` once you have saved the file. The artifact is the file, not your report. Do not echo the draft back, do not summarize the changes, do not narrate." Verbose subagent returns bloat the orchestrator's context across rounds and cause the loop to lose track of state.

Wait for the writer to finish before starting the reviewer.

### Step 2 — Reviewer pass

Spawn a reviewer subagent. Prefer `subagent_type=critic` if available; fall back to `code-reviewer`, then `executor`. Give the reviewer:

- The exact `draft_path` to read.
- The topic, purpose, audience, and review angle (so it can judge fit, not just surface prose).
- The reviewer persona — load it from `references/reviewer-prompt.md` and pass its contents into the subagent prompt verbatim. The persona is the soul of this skill; do not paraphrase it.
- The verdict contract: the reviewer must end its response with exactly one of these lines, on its own line, with no surrounding markdown:
  - `VERDICT: APPROVED` — the document is solid; no further revisions needed.
  - `VERDICT: REVISE` — preceded by a numbered list of concrete issues the writer must address.
- A reminder to keep the response focused: "Return only the numbered critique followed by the verdict line. Do not preface with 'Here is my review' or close with 'Hope this helps'. Long preambles bloat the orchestrator's context."

Do **not** pass the previous draft alongside the new one. The reviewer judges the current draft on its own terms, not as an improvement-grading exercise.

Wait for the reviewer to finish, then parse its output for the verdict line.

### Step 3 — Decide

Parse the reviewer's verdict using a tolerant matcher: the regex `/^\s*\**\s*VERDICT:\s*(APPROVED|REVISE)\s*\**\s*\.?\s*$/im` against the response. This accepts `VERDICT: APPROVED`, `**VERDICT: REVISE**`, `VERDICT: REVISE.`, etc. — critic-style agents frequently bold or punctuate the line despite the contract.

Then act on the parsed verdict:

- **`APPROVED`** → loop ends. Tell the user the document was approved at round N and where to find it. Show the user a 2-3 line summary of the headline changes the reviewer pushed for over the rounds.
- **`REVISE`** →
  - Save everything before the verdict line (the numbered critique) as `last_critique`.
  - If `round < max_rounds` → increment `round` and **immediately invoke Step 1 in the same orchestrator turn**. Do not write a status message, do not summarize the round, do not address the user between rounds. The only user-facing output between rounds is a single short line like `→ round N` so the user can see progress; everything else stays silent until APPROVED or the cap is hit. Round boundaries are the most common silent-halt point because the orchestrator treats them as natural turn ends — resist that.
  - If `round == max_rounds` → loop ends with cap reached. Show the user the final draft path, the unresolved critique, and ask: (a) accept the draft as-is, (b) extend the cap by N more rounds, or (c) abandon. Don't keep looping silently.
- **No parseable verdict** → don't guess. Re-prompt the same reviewer subagent and quote its actual final lines back so it can see what it produced: "Your response ended with: `<paste last 3 lines>`. The orchestrator's verdict parser requires a line matching `VERDICT: APPROVED` or `VERDICT: REVISE` exactly — no bold, no markdown, no trailing punctuation. Append a corrected verdict line." If it fails twice, stop the loop and surface the issue to the user along with the reviewer's raw output.

## Anti-patterns

- **Don't sanitize the critique before passing it to the writer.** Harsh stays harsh; softening defeats the loop.
- **Don't be the reviewer yourself.** You're too close and too eager to please the user — spawn a real subagent every round.

## Driving with ralph (recommended for long runs)

The in-prose loop above is fragile: round boundaries are natural turn ends, and a single distracted response can silently halt the iteration. For high-stakes documents or large round caps (>3), drive `grill-and-revise` under the `oh-my-claudecode:ralph` skill instead — ralph's hook system emits "The boulder never stops" continuation signals that prevent the orchestrator from drifting into a final-looking summary mid-loop.

To invoke under ralph:

1. Persist loop state to a sidecar file alongside the draft: `<draft_path>.grill.json` with shape `{ "round": N, "max_rounds": M, "verdict": "REVISE|APPROVED|null", "last_critique": "...", "draft_path": "..." }`. Update it after every reviewer pass. This is what survives across ralph iterations.
2. Hand ralph a single user story whose acceptance criterion is: `"<draft_path>.grill.json shows verdict=APPROVED, OR round>=max_rounds with user explicitly accepting the cap"`. Refine the auto-generated PRD scaffold to this exact criterion — do not leave the generic "Implementation is complete" placeholder.
3. Each ralph iteration reads the sidecar, picks up at the recorded round, runs one writer + reviewer pass (Steps 1–2 above), updates the sidecar, and lets ralph's continuation hook fire the next iteration. The orchestrator never has to "decide to keep going" — ralph's hook does.
4. Pass `--no-deslop` to ralph: the deslop pass is for *code* cleanup and is not appropriate for prose drafts. Without this flag ralph will run `ai-slop-cleaner` on your document, which is the wrong tool.
5. Optionally pass `--critic=critic` so ralph's own approval reviewer at Step 7 is the same critic flavor as the in-loop reviewer; this keeps the verdict semantics consistent.

When *not* to use ralph: round caps of 1–2, or one-off interactive runs where you want to read each round's critique as it lands. The plain in-prose loop is simpler for those.

## After the loop

Show the final draft path and a 2-3 line summary (rounds taken, headline changes, unresolved concerns). Don't auto-commit, auto-publish, or auto-send.

## Reference files

- `references/reviewer-prompt.md` — the reviewer persona. Load and pass to every reviewer subagent verbatim.
