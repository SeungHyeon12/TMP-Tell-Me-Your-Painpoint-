# TMP — Tell Me your Painpoint

A Claude Code plugin for **persona-based automated UX walkthroughs**.

Point it at a URL and a set of diverse persona agents (a nervous first-timer, an impatient
power user, an accessibility-dependent user, a mobile visitor, a trust-sensitive skeptic —
plus any custom persona you define) each drive a **real browser** through your site. Every
persona records their *aha-moments*, *pain points*, and where they'd likely give up. The
findings are synthesized into a single **interactive HTML dashboard**.

> **What this is — and isn't.** Results are *predicted, heuristic* judgments from simulated
> personas (an automated cognitive walkthrough / heuristic evaluation), **not** measured
> behavioral data from real users. Use it as a cheap pre-launch screening pass, not as a
> replacement for real user testing.

## Usage

```
/tmp-ux:ux-review <url> [--goal "reach first value"] [--personas ...] [--custom "..."]
```

This is a **goal-oriented First-Run** evaluation: each persona pursues a concrete goal (reaching
the product's first value) directly, on a short budget, and reports where they get stuck on the
way (Cognitive Walkthrough). There is no free-exploration mode — for first-run, wandering is cost,
not signal. (Repeat-visit wandering *is* the signal for the separate decay loop below.)

- **--goal** — what each persona tries to reach; defaults to "reach the product's first
  meaningful value / core action".
- **--personas** — pick from the 5 defaults (`novice,power,a11y,mobile,skeptic`); default is all.
- **--custom** — add your own persona; if it's vague, the plugin refines it and asks you to
  approve the line-up before running.

Example:

```
/tmp-ux:ux-review https://example.com --goal "find and start the free trial"
```

## How it works

1. The `/ux-review` command parses your request and (for custom personas) gets your approval.
2. Persona runners execute **one at a time** — they share a single Playwright browser — each
   returning a structured JSON verdict.
3. A synthesizer merges cross-persona issues, ranks them by severity × reach, and builds the
   dashboard, which is published as an Artifact.

## Requirements

- The bundled **Playwright MCP** server (`npx @playwright/mcp@latest`) — starts automatically
  when the plugin is enabled. Node.js / npx must be available on your machine.
- **Python 3** on your `PATH` (standard library only) — used to aggregate persona scores.

## Project layout

```
.claude-plugin/plugin.json   # manifest
.mcp.json                    # Playwright MCP server
skills/
  ux-review/SKILL.md               # orchestrator skill (auto-invocable + /tmp-ux:ux-review)
  ux-review-one-persona-loop/      # single-persona interest-decay loop (up to 7 visits)
    SKILL.md
agents/
  ux-persona-runner.md       # generic single-persona walkthrough executor
  ux-synthesizer.md          # semantic synthesis + dashboard builder
  ux-decay-runner.md         # one repeat-visit for the interest-decay loop
scripts/
  aggregate.py               # deterministic score aggregation (Python, stdlib only)
  decay_slope.py             # least-squares interest-decay slope (Python, stdlib only)
shared/
  default-personas.md        # the 5 default persona profiles
  persona-protocol.md        # browsing protocol + output schema + scoring rubric
  decay-personas.json        # persona set + config for the decay loop
```

## Interest-decay loop (`/tmp-ux:ux-review-one-persona-loop`)

A second skill measures **repeat-visit decay** for a single persona: the same persona visits the
site up to **7 times**, the browser is reset to a first-time visitor each visit, but the persona
*remembers* how often it has been — so novelty wears off like a real user. It self-reports interest
(0–100) each visit; `scripts/decay_slope.py` computes the least-squares **decay slope** (negative =
interest fades on repeat). Two nested loops: outer over visits (≤ 7), inner over actions per visit.

```
/tmp-ux:ux-review-one-persona-loop https://example.com --persona busy_operator --iterations 7
```

### Scoring: LLM judges, code counts

Each persona returns raw 1–5 scores (including the six **First-Run AX** dimensions). The exact
aggregation — First-Run AX Score, per-dimension averages, friction, retention — is done by
`scripts/aggregate.py` (Python standard library only), so the numbers are exact and
reproducible rather than eyeballed by the model. The model does the judgment; the script does
the arithmetic.
