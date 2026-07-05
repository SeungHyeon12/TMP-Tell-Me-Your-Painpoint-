---
name: ux-review
description: Run a persona-based automated UX walkthrough of a website. Diverse persona agents drive a real browser through the site and their findings (aha-moments, pain points, predicted friction) are synthesized into an interactive dashboard. Use when the user wants to evaluate or review a website's UX/usability, find pain points or friction, do a heuristic evaluation or cognitive walkthrough, or test a site with user personas.
argument-hint: <url> [--mode freeroam|task] [--task "goal"] [--personas novice,power,a11y,mobile,skeptic] [--custom "persona description"]
---

Orchestrate a persona-based UX review. User input: `$ARGUMENTS`

## Parse the request

- **url** (required): the site to evaluate. If missing, ask for it and stop.
- **--mode**: `freeroam` (default) or `task`.
- **--task**: the goal string, required when mode is `task` (e.g. "complete signup").
  If mode is `task` but no goal is given, ask for it before running.
- **--personas**: comma list from the 5 defaults in
  `${CLAUDE_PLUGIN_ROOT}/shared/default-personas.md`. Default = all five.
- **--custom**: one or more free-text persona descriptions to add or use instead.

## Handle custom personas (approval gate)

If the user supplied custom personas: read them, and if any are thin or vague, **refine them**
into full profiles in the same shape as the default-personas file (who / behavior / aha
triggers / bad triggers). Then present the final persona line-up (defaults + refined customs)
to the user and **wait for explicit approval** before running anything. Do not start the
walkthroughs until the user confirms the persona set.

## Confirm the plan

Briefly state: URL, mode (+ goal if task), and the persona line-up. Remind the user that
results are **predicted heuristic** judgments, not measured user data. Then proceed.

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
