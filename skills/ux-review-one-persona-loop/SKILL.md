---
name: ux-review-one-persona-loop
description: Measure how fast a single persona's interest decays on repeated exposure to a site. Runs ONE chosen persona through up to 7 repeat visits (fresh browser each time, persistent agent memory), self-reporting interest per visit, then computes the least-squares interest-decay slope. Use when the user wants to measure repeat-visit retention, novelty decay, cold-start staleness, or an interest-decay slope for one persona.
argument-hint: <url> [--persona busy_operator|curious_explorer|skeptical_first_timer|custom] [--iterations 1-7] [--goal "task goal"]
---

Run a single-persona interest-decay loop. User input: `$ARGUMENTS`

This measures repeat-exposure decay: the same persona visits the site several times; the browser
is reset to a first-time visitor each visit, but the persona **remembers** how many times it has
been, so novelty wears off exactly like a real user. The output is a **decay slope** (negative =
interest fades on repeat).

# MANDATORY INTAKE — always run first, never skip

Confirm all four before any browser action (args are pre-fills only; still confirm):

1. **url** (required). If missing, ask and stop.
2. **One persona** — this loop runs for EXACTLY ONE persona. Read
   `${CLAUDE_PLUGIN_ROOT}/shared/decay-personas.json`, present the available personas (id + the
   "what bores them" gist) in one line each, and ask the user to pick ONE — or to define a custom
   persona. If the custom one is thin, refine it (persona + task_goal + what makes them lose
   interest) and show it back for approval.
3. **iterations** — default **7**, allowed range **1–7**. This is a HARD CAP: never run more than
   7 visits. If the user asks for more, clamp to 7 and tell them.
4. **goal** — use the persona's `task_goal`, or the `--goal` override; confirm it.

Then restate the plan (url, persona, N visits, goal) and note that interest scores are **predicted
heuristic** self-reports, not measured analytics. Proceed only after confirmation.

## Run the loop — TWO nested loops, sequential

**Outer loop** (visits 1..N, N ≤ 7): keep a running `memory` list, starting empty. For each visit
`i`, invoke the `tmp-ux:ux-decay-runner` agent — one at a time, waiting for each to finish (they
share one browser) — passing:

- the chosen persona (persona text + task_goal) and the url,
- `visitNumber = i`, `totalVisits = N`,
- `memory` = the array of prior visits' `summary` strings,
- `maxSteps` = `max_steps_per_session` from the config (default 8) — this is the **inner loop**
  the runner executes.

After each visit, append the returned `summary` to `memory` (this is where decay accumulates) and
record the returned visit object. Never reset `memory` between visits — only the browser resets.

## Compute the slope — deterministic (do NOT eyeball it)

Write the collected visits to a temp file, e.g.:

```json
{ "id": "<persona id>", "url": "<url>", "goal": "<goal>", "visits": [ <each returned visit obj> ] }
```

at `${CLAUDE_PROJECT_DIR}/.decay-visits.json`, then run:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/decay_slope.py" "${CLAUDE_PROJECT_DIR}/.decay-visits.json"
```

Use its output (slope, verdict, interest series, drop) **verbatim** — do not recompute the slope.

## Report

Give the user: the persona, the interest series across visits (e.g. `85 → 70 → … → 30`), the
**decay slope** and its verdict, first→last drop, and how many visits completed the goal. Add one
or two sentences of interpretation grounded in the per-visit summaries (what specifically made
interest fade or hold). If `warnings` are present, surface them.
