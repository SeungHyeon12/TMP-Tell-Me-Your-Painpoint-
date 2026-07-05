---
name: ux-review
description: Run a goal-oriented, persona-based First-Run UX evaluation of a website. Diverse persona agents each pursue a concrete goal (reaching the product's first value) on a short budget via a real browser, and their findings (aha-moments, pain points, predicted friction, First-Run AX score) are synthesized into an interactive dashboard. Use when the user wants to evaluate a site's first-run experience, whether users reach first value, find onboarding pain points or friction, do a cognitive walkthrough, or test a site with user personas.
argument-hint: <url> [--goal "reach first value"] [--personas novice,power,a11y,mobile,skeptic] [--custom "persona description"]
---

Orchestrate a persona-based UX review. User input: `$ARGUMENTS`

# INTAKE — defaults run directly; only customization needs approval

Only the **url** is a hard prerequisite: if no URL is given, ask for it first and stop.

**Default behavior is to just run.** If the user only gives a URL (or a URL plus `--goal`), run
immediately with all 5 default personas and the goal below — do NOT block on a confirmation
prompt. You only pause for explicit approval when the user adds a **custom** persona (Step 2.3).
Never force a plain default run behind an `AskUserQuestion`.

## Step 1 — Goal (always goal-oriented)

This is a **First-Run** evaluation: it measures whether personas **reach the product's first
value**, not how long they wander. There is no free-exploration mode — always run to a goal.

Use the user's `--goal` if given; otherwise default to **"reach the product's first meaningful
value / core action"** and proceed. Only ask the user (via `AskUserQuestion`) if the request is
genuinely ambiguous about what "first value" means for this site. Personas pursue the goal
directly on a short budget (6–8 steps); wandering is treated as cost.

## Step 2 — Personas: default to all 5, approve only customization

1. **Default line-up is all 5** (from `${CLAUDE_PLUGIN_ROOT}/skills/ux-review/shared/default-personas.md`):
   novice (nervous first-timer) · power (impatient power user) · a11y (accessibility-dependent) ·
   mobile (on-the-go phone user) · skeptic (trust/price-sensitive). If the user did not ask to
   customize personas, run all 5 as-is — do not prompt.
2. **If the user picked a subset** (via `--personas` or in their request), run exactly that subset.
3. **If the user adds a custom persona:** read their description, and if it's thin or vague,
   **refine it** into a full profile in the same shape as the default-personas file
   (who / behavior / aha triggers / bad triggers). Then present the final persona line-up
   (chosen defaults + refined customs) back to the user and **get explicit approval before
   running.** If they want changes, revise and re-confirm.

## Confirm and go

Briefly restate the plan (URL, the goal, final persona line-up) and remind the user that results
are **predicted heuristic** judgments, not measured user data. For a plain default run this is a
one-line heads-up, not a blocking question; for a custom line-up, proceed only after the approval
in Step 2.3. Then run.

## Run the walkthroughs — SEQUENTIALLY

The personas share ONE Playwright browser, so they MUST run one at a time. For each persona,
in turn, invoke the `tmp-ux:ux-persona-runner` agent and WAIT for it to finish before
starting the next. Never launch persona runners in parallel.

Pass each runner:
- the full persona profile block (from default-personas.md, or the approved custom profile),
- the target url,
- the confirmed goal,

and ask it to follow `${CLAUDE_PLUGIN_ROOT}/skills/ux-review/shared/persona-protocol.md` (goal-oriented, short
budget) and return its JSON verdict. Collect each returned JSON object.

If a runner returns malformed JSON or dies, note it and continue with the remaining personas.

## Aggregate the scores — deterministic (do NOT do this math yourself)

Once all personas are done, write the collected array of verdict JSON objects to a temp file
(e.g. `${CLAUDE_PROJECT_DIR}/.ux-verdicts.json`) and run:

```
python "${CLAUDE_PLUGIN_ROOT}/skills/ux-review/scripts/aggregate.py" "${CLAUDE_PROJECT_DIR}/.ux-verdicts.json"
```

This prints an exact metrics JSON (overall First-Run AX Score, per-dimension averages, weakest
dimension, the **stop-reason gate** — done/budget_cut/stuck counts, scored-session count, and any
personas flagged for re-run — plus friction average and retention counts). **Use these numbers
verbatim** — never recompute averages by hand. Note the gate: only `done` sessions are clean
first-value successes, `budget_cut` sessions are first-value failures (their value dims were capped
low), and `stuck` sessions were excluded. If the output contains `warnings`, surface them but
continue. If `rerunNeeded` is non-empty, tell the user those personas got stuck and could be re-run.

## Synthesize and publish

Invoke the `tmp-ux:ux-synthesizer` agent with (a) the array of per-persona verdicts, (b) the
precomputed metrics JSON from the aggregate script, and (c) the url and goal. It writes an
interactive dashboard to `${CLAUDE_PROJECT_DIR}/ux-report.html` and returns a summary.

Then publish that file with the **Artifact** tool so the user gets a shareable dashboard.

Finally, give the user a short text recap: the **First-Run AX Score** (1–5) with its weakest
dimension, the **stop-reason gate** (how many personas reached first value / done vs budget_cut vs
stuck), the headline verdict, the top 3 issues (severity + affected personas + fix), and the
strongest aha-moment. Point them to the dashboard for detail.
