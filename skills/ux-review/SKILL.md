---
name: ux-review
description: Run a persona-based automated UX walkthrough of a website. Diverse persona agents drive a real browser through the site and their findings (aha-moments, pain points, predicted friction) are synthesized into an interactive dashboard. Use when the user wants to evaluate or review a website's UX/usability, find pain points or friction, do a heuristic evaluation or cognitive walkthrough, or test a site with user personas.
argument-hint: <url> [--mode freeroam|task] [--task "goal"] [--personas novice,power,a11y,mobile,skeptic] [--custom "persona description"]
---

Orchestrate a persona-based UX review. User input: `$ARGUMENTS`

# MANDATORY INTAKE — always run this first, never skip

**This skill ALWAYS begins with the two-step intake below.** Even if the user already passed
`--mode`, `--task`, or `--personas` in their input, treat those only as pre-filled defaults —
you must still explicitly confirm BOTH decisions with the user. **Do not open the browser,
invoke any persona runner, or take any other action until the user has confirmed both Step 1
and Step 2.** If you ever find yourself about to run a walkthrough without both confirmations,
stop and return to this intake.

Only the **url** is a hard prerequisite: if no URL is given, ask for it first and stop.

## Step 1 — Mode: goal-driven or free exploration?

Ask the user (use the `AskUserQuestion` tool) which mode to run, pre-selecting whatever the
input implied:

- **task (goal-driven)** — personas attempt a specific goal and report where they get stuck.
  If they pick this, you MUST get the concrete goal (e.g. "complete signup", "find pricing")
  before proceeding.
- **freeroam (free exploration)** — personas explore with no goal and report general
  impressions and friction.

Do not assume a mode. Wait for the answer (and the goal, if task).

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

Once both steps are confirmed, briefly restate the plan (URL, mode + goal if task, final
persona line-up) and remind the user that results are **predicted heuristic** judgments, not
measured user data. Then proceed to run.

## Run the walkthroughs — SEQUENTIALLY

The personas share ONE Playwright browser, so they MUST run one at a time. For each persona,
in turn, invoke the `tmp-ux:ux-persona-runner` agent and WAIT for it to finish before
starting the next. Never launch persona runners in parallel.

Pass each runner:
- the full persona profile block (from default-personas.md, or the approved custom profile),
- the target url,
- the mode,
- the goal (task mode only),

and ask it to follow `${CLAUDE_PLUGIN_ROOT}/shared/persona-protocol.md` and return its JSON
verdict. Collect each returned JSON object.

If a runner returns malformed JSON or dies, note it and continue with the remaining personas.

## Synthesize and publish

Once all personas are done, invoke the `tmp-ux:ux-synthesizer` agent with the array of
per-persona JSON verdicts plus the url and mode. It writes an interactive dashboard to
`${CLAUDE_PROJECT_DIR}/ux-report.html` and returns a summary.

Then publish that file with the **Artifact** tool so the user gets a shareable dashboard.

Finally, give the user a short text recap: the headline verdict, the top 3 issues (severity +
affected personas + fix), and the strongest aha-moment. Point them to the dashboard for detail.
