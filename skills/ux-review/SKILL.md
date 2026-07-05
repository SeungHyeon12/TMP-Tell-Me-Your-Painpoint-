---
name: ux-review
description: Run a goal-oriented, persona-based First-Run UX evaluation of a website. Diverse persona agents each pursue a concrete goal (reaching the product's first value) on a short budget via a real browser, and their findings (aha-moments, pain points, predicted friction, First-Run AX score) are synthesized into an interactive dashboard. Use when the user wants to evaluate a site's first-run experience, whether users reach first value, find onboarding pain points or friction, do a cognitive walkthrough, or test a site with user personas.
argument-hint: <url> [--goal "reach first value"] [--personas novice,power,a11y,mobile,skeptic] [--custom "persona description"]
---

Orchestrate a persona-based UX review. User input: `$ARGUMENTS`

# MANDATORY INTAKE — always run this first, never skip

**This skill ALWAYS begins with the two-step intake below.** Even if the user already passed
`--goal` or `--personas` in their input, treat those only as pre-filled defaults — you must
still explicitly confirm BOTH decisions with the user. **Do not open the browser, invoke any
persona runner, or take any other action until the user has confirmed both Step 1 and Step 2.**
If you ever find yourself about to run a walkthrough without both confirmations, stop and return
to this intake.

Only the **url** is a hard prerequisite: if no URL is given, ask for it first and stop.

## Step 1 — Goal (this run is always goal-oriented)

This is a **First-Run** evaluation: it measures whether personas **reach the product's first
value**, not how long they wander. So there is no free-exploration mode — always run to a goal.

Ask the user (use the `AskUserQuestion` tool) for the concrete goal each persona should pursue
(e.g. "reach the core action", "complete signup", "find pricing"). Offer a sensible default of
**"reach the product's first meaningful value / core action"** and let them accept or replace it.
Personas pursue this goal directly on a short budget (~5 steps); wandering is treated as cost.

## Step 2 — Personas: explain defaults, offer custom, get approval

1. **Explain the default line-up.** Read `${CLAUDE_PLUGIN_ROOT}/shared/default-personas.md` and
   present the 5 defaults to the user in one short line each:
   novice (nervous first-timer) · power (impatient power user) · a11y (accessibility-dependent) ·
   mobile (on-the-go phone user) · skeptic (trust/price-sensitive).
2. **Ask** (use `AskUserQuestion`) whether they want: all 5 defaults, a subset, and/or to add
   their own **custom persona(s)**.
3. **If they add a custom persona:** read their description, and if it's thin or vague,
   **refine it** into a full profile in the same shape as the default-personas file
   (who / behavior / aha triggers / bad triggers). Then present the final persona line-up
   (chosen defaults + refined customs) back to the user.
4. **Get explicit approval of the final line-up.** Do not proceed until the user confirms it.
   If they want changes, revise and re-confirm.

## Confirm and go

Once both steps are confirmed, briefly restate the plan (URL, the goal, final persona line-up)
and remind the user that results are **predicted heuristic** judgments, not measured user data.
Then proceed to run.

## Run the walkthroughs — SEQUENTIALLY

The personas share ONE Playwright browser, so they MUST run one at a time. For each persona,
in turn, invoke the `tmp-ux:ux-persona-runner` agent and WAIT for it to finish before
starting the next. Never launch persona runners in parallel.

Pass each runner:
- the full persona profile block (from default-personas.md, or the approved custom profile),
- the target url,
- the confirmed goal,

and ask it to follow `${CLAUDE_PLUGIN_ROOT}/shared/persona-protocol.md` (goal-oriented, short
budget) and return its JSON verdict. Collect each returned JSON object.

If a runner returns malformed JSON or dies, note it and continue with the remaining personas.

## Aggregate the scores — deterministic (do NOT do this math yourself)

Once all personas are done, write the collected array of verdict JSON objects to a temp file
(e.g. `${CLAUDE_PROJECT_DIR}/.ux-verdicts.json`) and run:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/aggregate.py" "${CLAUDE_PROJECT_DIR}/.ux-verdicts.json"
```

This prints an exact metrics JSON (overall First-Run AX Score, per-dimension averages, weakest
dimension, friction average, retention counts). **Use these numbers verbatim** — never recompute
averages by hand. If the output contains `warnings`, surface them (a persona returned an invalid
or missing score) but continue.

## Synthesize and publish

Invoke the `tmp-ux:ux-synthesizer` agent with (a) the array of per-persona verdicts, (b) the
precomputed metrics JSON from the aggregate script, and (c) the url and goal. It writes an
interactive dashboard to `${CLAUDE_PROJECT_DIR}/ux-report.html` and returns a summary.

Then publish that file with the **Artifact** tool so the user gets a shareable dashboard.

Finally, give the user a short text recap: the **First-Run AX Score** (1–5) with its weakest
dimension, the headline verdict, the top 3 issues (severity + affected personas + fix), and the
strongest aha-moment. Point them to the dashboard for detail.
