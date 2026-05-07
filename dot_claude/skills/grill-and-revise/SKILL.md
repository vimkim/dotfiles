---
name: grill-and-revise
description: "Iteratively improve a document by looping a writer subagent against a relentless reviewer subagent until the reviewer explicitly approves or a round cap is hit. Use whenever the user wants high-quality long-form writing (reports, design docs, JIRA issues, blog posts, technical analysis, RFCs, postmortems) and is willing to trade time for rigor — even when they don't say 'loop' or 'review', trigger this when they ask for a *thorough*, *bulletproof*, *peer-reviewed*, *grilled*, *stress-tested*, or *adversarially-reviewed* document, or when they explicitly ask to 'have another agent review' their writing, or say things like 'don't ship until it's solid'."
---

# Grill-and-Revise

A two-agent loop for producing rigorous documents. One subagent writes; another grills it relentlessly. The writer revises until the reviewer is satisfied — or a round cap stops the loop and hands control back to the human.

By default, the loop is driven by the `oh-my-claudecode:ralph` persistence engine, which uses hook-driven continuation to prevent silent halts at round boundaries. A simpler in-prose "lite" mode is available for short interactive runs.

## Why this exists

Single-pass writing tends toward hand-wavy, filler-heavy prose. A *separate* reviewer — one with no investment in defending the draft — catches what the writer missed; looping forces real iteration instead of cosmetic edits, and the explicit verdict keeps the loop honest. Self-review collapses into self-justification, which is why this skill always uses two distinct agents.

## When to use

Long-form writing where quality matters more than speed and the user will spend tokens on iteration. Skip short messages, code comments, or anything you could write in two sentences.

## When NOT to wrap with autopilot

Do not invoke this skill from `/oh-my-claudecode:autopilot`. Autopilot's QA cycle (build/lint/test) and Phase 4 reviewers (code-reviewer, security-reviewer) are calibrated for code, not prose, and will either skip silently or emit nonsense verdicts on documents.

The correct multi-stage pipeline for high-stakes writing is:

```
/oh-my-claudecode:deep-interview "vague topic"
  → Socratic Q&A produces a grounded brief
  → /grill-and-revise (ralph mode)
  → reviewer-approved draft
```

Mirror autopilot's structure (deep-interview → execution loop), not autopilot itself.

## Inputs to gather before launching

Ask the user (briefly, all at once) if these aren't already clear from context:

1. **Topic & purpose** — what is the document, and who is the audience?
2. **Output path** — where should the draft live? Default: `./drafts/<slug>.md` in the current working directory.
3. **Source material** — any reference files, transcripts, code, data, links the writer should ground in? Without this, the writer will fabricate confident-sounding filler and the reviewer will (correctly) tear it apart forever.
4. **Review angle** — what should the reviewer prioritize? Examples: technical accuracy, persuasiveness, clarity for non-experts, specific load-bearing claims to challenge. Default: general rigor — evidence, structure, clarity, no hand-waving.
5. **Round cap** — defaults to 5. The user can override.

Confirm before launching. The loop runs subagents and burns tokens; don't fire it speculatively from an ambiguous request.

### Preflight gate

If the user gave only a topic with no audience and no source material, **do not launch the loop**. Redirect to deep-interview first:

> "The brief is too thin to ground a writer — the reviewer will spend rounds tearing apart fabricated content. Run `/oh-my-claudecode:deep-interview "<topic>"` first to extract a structured brief, then re-launch grill-and-revise with the resulting spec."

Skip this gate only if the user has explicitly said "I know it's thin, run anyway" or has provided source material under #3.

## Mode selection

Choose the loop driver from the round cap:

- **`max_rounds ≥ 3`** → **Ralph mode (default)**. Hook-driven continuation prevents silent halts; PRD-backed state survives crashes.
- **`max_rounds ≤ 2`** → **Lite mode**. The in-prose loop below; cheaper to set up, no PRD scaffolding.

Do not ask the user which mode to use. Pick from `max_rounds` and proceed.

## Ralph mode (default)

Wrap the writer/reviewer cycle in a single ralph user story. Ralph's iteration loop fires writer + reviewer rounds until the acceptance criteria are met or the user cancels — its "boulder never stops" continuation hook removes the round-boundary silent-halt failure mode that the in-prose loop suffers from.

### Step R1 — Build the PRD

Write a PRD to ralph's session-scoped path (`.omc/state/sessions/{sessionId}/prd.json` if a session ID is available; fall back to `.omc/prd.json`). Use this exact shape:

```json
{
  "stories": [
    {
      "id": "US-001-grill-loop",
      "title": "Grill-and-revise <slug> until reviewer approves",
      "passes": false,
      "acceptanceCriteria": [
        "File exists at <draft_path> and starts with a ## TL;DR section of 3–5 plain-language lines",
        "Latest reviewer pass on <draft_path> emits a line matching /^\\s*\\**\\s*VERDICT:\\s*APPROVED\\s*\\**\\s*\\.?\\s*$/im",
        "Reviewer's last numbered critique list contains zero outstanding items"
      ],
      "context": {
        "draft_path": "<draft_path>",
        "topic": "<topic>",
        "audience": "<audience>",
        "review_angle": "<review_angle>",
        "source_material": ["<paths or inline refs>"],
        "max_rounds": <N>
      }
    }
  ]
}
```

Substitute the real values from the gathered inputs. The acceptance criteria are concrete enough to satisfy ralph's "no generic boilerplate" gate (ralph SKILL.md, Step 1c).

### Step R2 — Launch ralph

Invoke ralph with two non-negotiable flags:

- **`--no-deslop`** — `ai-slop-cleaner` is calibrated for code and will mangle prose. This flag is not optional for grill-and-revise runs.
- **`--critic=critic`** — the `critic` agent is the right reviewer for prose. The `architect` agent (ralph's default) is calibrated for code architecture and emits low-signal critiques on documents. This flag is not optional either.

Refuse to launch ralph if either flag is missing. If a caller tries to override `--critic=architect` or omit `--no-deslop`, surface the issue to the user before proceeding.

Example invocation:

```
/oh-my-claudecode:ralph --no-deslop --critic=critic "Drive the grill-and-revise loop on the PRD at <prd_path>. Each iteration: spawn one writer subagent, then one reviewer subagent, then update <draft_path>.grill.json with the verdict and critique. Continue until US-001-grill-loop has passes: true."
```

### Step R3 — Per-iteration body (what ralph runs each round)

Inside each ralph iteration, run exactly one writer pass and one reviewer pass, in sequence:

1. **Writer pass** — same as Lite mode Step 1 below. Spawn `subagent_type=executor` with `model=opus` for technically dense topics, `sonnet` otherwise. Pass the topic, source material, `draft_path`, the TL;DR requirement, and (on rounds ≥ 2) the reviewer's last critique. The writer must return only `OK` after saving the file.

2. **Reviewer pass** — same as Lite mode Step 2 below. Spawn `subagent_type=critic` (or `code-reviewer` / `executor` as fallback) with the persona from `references/reviewer-prompt.md`, the verdict contract, and the review angle.

3. **Persist state** — update the sidecar `<draft_path>.grill.json` with `{ round, verdict, last_critique }` so the next iteration's writer can read the prior critique. This sidecar is a *cache* for the writer; the PRD remains the source of truth for ralph.

4. **Update the PRD** — if the reviewer emitted `VERDICT: APPROVED` AND the critique list is empty, set `passes: true` on US-001-grill-loop. Otherwise leave `passes: false` so ralph continues iterating.

Ralph's continuation hook ("The boulder never stops") fires the next iteration automatically. The orchestrator does not have to "decide to keep going" between rounds — that is the entire point of ralph mode.

### Step R4 — Ralph's final verification

When the story flips to `passes: true`, ralph runs its own Step 7 reviewer pass against the acceptance criteria. With `--critic=critic`, this is the same critic flavor used in the per-round loop, so the verdict semantics line up. The mandatory deslop pass at ralph Step 7.5 is skipped because of `--no-deslop`. Ralph then exits via `/oh-my-claudecode:cancel`.

### Round cap handling

If iterations reach `max_rounds` without `VERDICT: APPROVED`, ralph will keep iterating because acceptance criteria are unmet. To enforce the cap, the per-iteration body must check the round counter in the sidecar before launching the writer: if `round >= max_rounds`, stop the loop and surface to the user. Ask: (a) accept the draft as-is, (b) extend the cap, or (c) abandon. Do not silently keep iterating past the cap.

### Multi-reviewer panel (optional)

For high-stakes documents, the per-iteration reviewer pass can fan out to multiple critics in parallel via ultrawork-style fire-all-at-once delegation:

- Pass `--reviewers=critic,architect,security-reviewer` (or any subset of available agent types) when launching grill-and-revise.
- In Step R3 (Reviewer pass), spawn N reviewer subagents in a single message — one per reviewer in the list — each with the same draft and review angle but its own persona.
- Merge the numbered critiques into a single deduplicated list before persisting to the sidecar.
- Emit `VERDICT: APPROVED` only when **all** reviewers approve. Any single `VERDICT: REVISE` keeps the story `passes: false`.

Single-critic remains the default. The panel is opt-in; do not enable it without explicit `--reviewers=...` from the user.

## Lite mode (max_rounds ≤ 2)

For one-off interactive runs where you want to read each round's critique as it lands, drive the loop in-prose without ralph.

Track this state across rounds:

- `draft_path` — file the writer writes to and the reviewer reads.
- `round` — starts at 1, increments each cycle.
- `max_rounds` — must be ≤ 2 for Lite mode; otherwise switch to Ralph mode.
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
- **Don't wrap this skill with autopilot.** Autopilot's code-oriented QA and reviewer phases will misfire on prose. Use the `deep-interview → grill-and-revise` pipeline instead.
- **Don't drop `--no-deslop` or `--critic=critic` in ralph mode.** The defaults are wrong for prose and will silently degrade the output.

## After the loop

Show the final draft path and a 2-3 line summary (rounds taken, headline changes, unresolved concerns). Don't auto-commit, auto-publish, or auto-send.

## Reference files

- `references/reviewer-prompt.md` — the reviewer persona. Load and pass to every reviewer subagent verbatim.
