---
name: verify-herdr-tab-labels
description: Model-check that herdr-tab-status never loses a user's Herdr tab name through crashes, lost or rejected rename replies, failed journal saves, restarts, and stop. It searches every order of those events up to a bound while running the real Updater code. Use when a change touches private_dot_local/bin/executable_herdr-tab-status in original_label, build_plan, Updater (__init__, save, update, restore), the error handling in run_events or main, the label journal (state.json), or the tab label format.
---

# Verify herdr-tab-status tab names

**Property.** At every moment, the on-disk journal plus the label Herdr shows give back the name the user chose for each tab, and a completed `stop` shows exactly those names with an empty journal.

**Harm when it breaks.** A crash or restart turns a decorated label into the tab's "original" name: the tab becomes `1 1 work [▶ Codex <1m] [▶ Codex <1m]`, and `stop` restores the decoration instead of `work`, so the user's name is gone for good.

`check.py` is a bounded model checker. It loads the real script and replaces only `request` (the Herdr socket call, with an in-memory Herdr) and `time` (a model clock). Breadth-first search then runs every order of updater steps, faults, and user actions within the bounds, and checks three properties after every step:

- `NameRecoverable`: for every tab, the real `original_label(live label, on-disk record)` returns the name the user chose.
- `StopRestores`: after a stop that finished without a fault, every tab shows the user's name, and the journal has no tab records.
- `JournalReadable`: a worker can always load the on-disk journal.

The search is a model checker over the real code, not over a hand model. The risk sits in the label-matching code (`original_label` and the journal's labels, suffixes, and prefixes), and a TLA+ model would have to re-implement that matching. The checker needs only the Python standard library. It was confirmed with Python 3.14.6.

## Does a change touch the verified code?

```bash
git diff 5b7f70c -- private_dot_local/bin/executable_herdr-tab-status   # committed and uncommitted changes
```

Coverage, confirmed at sync commit **5b7f70c**, where the script last changed. Line numbers are at that commit.

| Code | Role in the check |
| --- | --- |
| `original_label` (:282) | Runs as-is. It also judges `NameRecoverable`. |
| `build_plan` (:312) | Runs as-is inside `update`. |
| `Updater.__init__` (:409) | Runs as-is. It loads and validates `state.json`. |
| `Updater.save` (:453) | Runs as-is (temporary file plus `replace`). Only `os.fsync` is a no-op. |
| `Updater.update` (:471) | Runs as-is. One search step is one full call. |
| `Updater.restore` (:548) | Runs as-is for both `stop` paths: the worker's `finally` (:756) and `stop` with no worker (:743). |
| `run_events` error handling (:648) | Modeled: `OSError`, `ValueError`, `KeyError`, and `HerdrError` leave the worker alive with its in-memory journal. Anything else ends the run. |
| `request` (:242) | Replaced by the in-memory Herdr in `check.py`. |

A change outside these rows, such as the event feed, metadata tokens, or the lock and control socket, does not need this check.

## Run it

From the repository root:

```bash
python3 .claude/skills/verify-herdr-tab-labels/check.py      # all faults, depth 5, ~40 s; stops at the first counterexample
python3 .claude/skills/verify-herdr-tab-labels/mutants.py    # proves the check can still fail, ~5 s
```

Baseline at 5b7f70c:

- `check.py` prints `PASS ... within depth 5` with 11517 states. Any `FAIL` is new.
- `mutants.py` prints `CAUGHT` for all seven mutants.

Run both on every change that touches the covered code. Use `--depth 6` (about 2 minutes) before merging a change to `update`, `restore`, or `original_label`. Use `--script PATH` to check another copy of the script. `--no-save-faults` leaves out failed journal saves; use it only to tell whether a counterexample depends on one.

## Reading a result

A `FAIL` prints the property and a numbered trace. Each step names what ran (`update()`, `stop: restore()`, a user action, or a fault) with the renames Herdr applied, followed by the labels, the journal's base names on disk, whether the worker's journal differs from the disk, and the names the user chose.

To tell a real bug from a modeling error, replay the trace against the code:

- **Real bug.** Every step is something the real system can do, and the code does what the trace says. Report it with the trace in these words. Leave the property and the bounds unchanged.
- **Modeling error.** A step is impossible for the real system. For example, the in-memory Herdr's snapshot or rename semantics differ from the `HerdrServer` fixture in `tests/test_herdr_tab_status.py`, or the trace needs a user rename inside a single `update()` call (the documented race below). Fix `check.py`, then rerun `mutants.py`.
- `STALE` from `mutants.py` means the code changed under a mutant's snippet. Update the snippet so it breaks the same rule again. `MISSED` means the check no longer catches that rule. Treat it as a hole in the check and fix it before trusting a `PASS`.

## Scope and bounds

- Two tabs in one workspace: `w1:t1`, named `work` with an agent, and `w1:t2`, named `7` (a numeric name) with none.
- User actions, each between updater steps: rename a tab to `notes`; edit a decorated label to `N notes [suffix]`, keeping the managed number and suffix; change an agent (absent, working, blocked); swap the tabs; let one minute pass.
- Faults, at most 2 per trace:
  - the journal save raises `OSError`;
  - the process dies right after the save;
  - the first or second `tab.rename` is rejected, has its reply lost after Herdr applied it, or the process dies just before or just after Herdr applies it;
  - the process dies between steps while its journal is unsaved.
- Depth 5 steps by default. A `--depth 6` run with all faults (43510 states, 265767 transitions, about 2 minutes) passed at 5b7f70c.
- Assumptions:
  - User renames never land inside one `update()` call. `docs/herdr-tab-status.md` documents that race ("A manual rename between a snapshot and its rename request can race the updater"), and the Herdr API has no conditional rename.
  - Timer updates reuse a cached snapshot that matches Herdr, because every rename event invalidates it. The model always takes a fresh snapshot.
  - Crashes are process deaths. `os.replace` stays atomic. Power loss and the missing directory `fsync` are out of scope.
- Not covered: metadata tokens and pane IDs, the event feed, the lock and control-socket lifecycle (`start` and `stop` delivery), and more than two tabs or workspaces.

A `PASS` covers these bounds, not every possible history.

## Findings

**F1, fixed in 5b7f70c: a failed journal save was not retried before renaming.**

`Updater.update` used to assign `self.tabs = journal` before `self.save()`. When the save raised (for example `ENOSPC` on `~/.cache`), `run_events` retried, the computed journal equaled `self.tabs`, and `update` renamed the tabs without saving. If the worker then died, the next worker renamed `work` to `1 1 work [▶ Codex <1m] [▶ Codex <1m]`, and `stop` restored `1 work [▶ Codex <1m]`.

The fix keeps the previous journal in memory until the save succeeds. Two things guard it: the mutant `keep-unsaved-journal`, and the test `test_failed_journal_save_is_retried_before_renaming` in `tests/test_herdr_tab_status.py`.

## Keeping it in step with the code

- When a change is intended (a new journal field, label format, Herdr call, or error type), update `check.py` to match:
  - the `Herdr` fake for new requests or snapshot fields;
  - `DECORATED` for a new label shape;
  - the caught exception tuple in `Model.run` for new error handling.
  Then rerun all three commands.
- Move the sync commit forward only after you have re-read every row of the coverage table at the new commit, confirmed the check still describes that code, and seen the baseline results. Update the line numbers in the table at the same time.
