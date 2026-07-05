---
name: ux-review-one-persona-loop
description: Measure how fast a single persona's interest decays on repeated exposure to a site. Runs ONE chosen persona through up to 7 repeat visits (fresh browser each time, persistent agent memory) and fits a least-squares decay slope to two per-visit signals -- primarily the behavioral, in-browser-observed count of structurally-new screens found, and secondarily the persona's self-reported interest. Use when the user wants to measure repeat-visit retention, novelty decay, cold-start staleness, or an interest-decay slope for one persona.
argument-hint: <url> [--persona busy_operator|curious_explorer|skeptical_first_timer|custom] [--iterations 1-7] [--goal "task goal"]
---

Run a single-persona interest-decay loop. User input: `$ARGUMENTS`

This measures repeat-exposure decay: the same persona visits the site several times; the browser
is reset to a first-time visitor each visit, but the persona **remembers** how many times it has
been, so novelty wears off exactly like a real user. The output is a behavioral **decay slope** —
new screens found per revisit, negative meaning the site stops surprising this persona — cross-checked
against a softer self-reported-interest slope.

# MANDATORY INTAKE — always run first, never skip

Confirm all four before any browser action (args are pre-fills only; still confirm):

1. **url** (required). If missing, ask and stop.
2. **One persona** — this loop runs for EXACTLY ONE persona. Read
   `${CLAUDE_PLUGIN_ROOT}/skills/ux-review-one-persona-loop/shared/decay-personas.json`, present the available personas (id + the
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
- `maxSteps` = `max_steps_per_session` from the config — a **generous circuit breaker**, NOT a
  target. The runner runs the **inner loop** and decides when to leave on its own.

**How each visit ends (this is the whole point — don't just run to `maxSteps`).** The runner
classifies its exit in `stopReason`, and here the moment of leaving IS the measurement:

- **bored / explored** — the persona left voluntarily (out of interest, or having seen it all).
  This is the clean signal, and it also controls cost: a bored persona leaves in 2–3 steps, so
  later visits get naturally short and cheap. Preserve this — never force the runner to keep going.
- **stuck** — wandering / spinning with no progress. The runner self-detects this (no page change
  over 3 actions, revisiting a state a 3rd time, or nothing new in 4 actions) and cuts immediately.
  **This is the real token lever** — it kills spinning sessions in a few steps so nothing runs away.
- **budget_cut** — hit the circuit breaker `maxSteps`. Should be rare.

Do NOT lower `maxSteps` to control cost — that would clip the naturally long early visits (real
signal). Cost is controlled by the wandering cut + voluntary leave, not by a tight ceiling. (For
rigor you can pilot once with a large cap to see where the persona naturally leaves, then set
`maxSteps` to ~2–3× that median.)

After each visit, append the returned `summary` to `memory` (this is where decay accumulates) and
record the returned visit object. Never reset `memory` between visits — only the browser resets.

## Compute the slope — deterministic (do NOT eyeball it)

Write the collected visits to a temp file, e.g.:

```json
{ "id": "<persona id>", "url": "<url>", "goal": "<goal>", "visits": [ <each returned visit obj> ] }
```

at `${CLAUDE_PROJECT_DIR}/.decay-visits.json`, then run:

```
python "${CLAUDE_PLUGIN_ROOT}/skills/ux-review-one-persona-loop/scripts/decay_slope.py" "${CLAUDE_PROJECT_DIR}/.decay-visits.json"
```

Each visit object MUST carry `stopReason`, `interest`, `newScreens`, `turns`, and `screenSignatures` (per-screen fingerprints the runner captured; the script counts new screens from them). Use the script's
output **verbatim** — do not recompute anything. It reports **two decay signals**, gated to
bored/explored sessions only (`stuck` excluded + listed in `rerunNeeded`; `budget_cut` censored):

- **`primaryBehavioral`** — slope of **newScreens** (structurally-distinct new screens per visit, counted in Python from the runner's in-browser fingerprints). This is
  the trustworthy signal: it is observed, not self-reported. Lead with it.
- **`secondarySelfReport`** — slope of self-reported **interest**. Soft evidence only — the persona
  was told to cool on repeat, so cross-check it against the behavioral slope, never quote it alone.

Each slope comes with `stdErr`, `r2`, and a `significance` verdict (`declining` / `rising` / `flat`
= indistinguishable from noise / `unpowered` = <3 clean points / `inconclusive` = <2). If the
behavioral slope is `inconclusive`, tell the user the run couldn't measure decay (too few clean
sessions) and suggest re-running.

## Report

Give the user: the persona, and BOTH series annotated with how each visit ended — newScreens
(e.g. `2 → 1 → 1 → 1 → 0`) and interest (e.g. `78(explored) → 32(bored) → …`). Lead with the
**behavioral decay** (primaryBehavioral slope ± stdErr, R², verdict); present the **self-reported
interest** slope second and explicitly as softer evidence. Call out when the two **diverge** (e.g.
interest crashes while newScreens only drifts — that gap is narrative, not observed decay). Then the
**stopReason breakdown** (bored/explored vs stuck vs budget_cut, and `cleanSessions`), any
`rerunNeeded` visits, and one or two sentences grounded in the per-visit summaries (what actually
stopped being new). If `warnings` are present, surface them.
