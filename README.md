# TMP — Tell Me your Painpoint

An **automated Heuristic Evaluation (HE) pre-screener** for websites, packaged as a Claude Code plugin.

Heuristic Evaluation is Nielsen's classic *discount* usability method: a few expert evaluators
inspect an interface against a set of heuristics and flag likely violations — **no real users
required.** TMP automates that first pass. Point it at a URL and a set of diverse persona agents
(a nervous first-timer, an impatient power user, an accessibility-dependent user, a mobile visitor,
a trust-sensitive skeptic — plus any custom persona you define) each drive a **real browser** through
your site as a *distinct evaluator lens*. Every persona pursues a concrete goal, tags each problem
with the Nielsen heuristic it violates, and records *aha-moments*, *pain points*, and where they'd
likely give up. The findings are synthesized into a single prioritized **interactive HTML dashboard**.

> **What this is — and isn't.** This is a **pre-screener**, not user testing. Results are *predicted,
> heuristic* judgments from an automated inspection (persona-lens HE + cognitive walkthrough), **not**
> measured behavioral data from real users. Its job is to catch the cheap, obvious heuristic
> violations *before* you spend scarce real-user-research budget — "AI for speed, humans for truth."
> Treat every score as a flag to investigate, never as a metric to report.

## Where it fits in your process

1. **Build / change** a flow.
2. **TMP pre-screen** (minutes, this plugin) → fix the heuristic violations it surfaces. Cheap,
   repeatable, run it on every iteration.
3. **Real-user testing** (expensive, slow) → spend it on the *hard* questions TMP can't answer
   (do people actually want this? does the value land?), not on catching obvious layout/label bugs.

TMP replaces the manual expert HE pass in step 2 — the discount screen — not the real users in step 3.

## Installation

Claude Code installs plugins by adding a **marketplace source** and then installing from it — there
is no central store to browse. This repo *is* the marketplace (it ships a `.claude-plugin/marketplace.json`).

**From GitHub** (for anyone; the repo must be public):

```
/plugin marketplace add SeungHyeon12/TMP-Tell-Me-Your-Painpoint-
/plugin install tmp-ux@tmp-ux
/reload-plugins        # or restart Claude Code
```

**From a local clone** (for development):

```
/plugin marketplace add /path/to/this/repo
/plugin install tmp-ux@tmp-ux
```

Or, to load it for a single session without installing: `claude --plugin-dir /path/to/this/repo`.

After installing, verify with `/plugin list` (tmp-ux enabled) and `/mcp` (the bundled **playwright**
server connected). On the first browser run, Playwright may need its browser binary — if so, run
`npx playwright install chromium`. See **Requirements** below for Node.js / Python prerequisites.

## Usage

```
/tmp-ux:ux-review <url> [--goal "reach first value"] [--personas ...] [--custom "..."]
```

This is a **goal-oriented First-Run** evaluation: each persona pursues a concrete goal (reaching
the product's first value) directly, on a short budget, and reports where they get stuck on the
way (Cognitive Walkthrough). There is no free-exploration mode — for first-run, wandering is cost,
not signal. (Repeat-visit wandering *is* the signal for the separate decay loop below.)

- **--goal** — what each persona tries to reach. If you omit it, the command asks you for one
  first (offering "reach the product's first meaningful value / core action" as the default to
  accept).
- **--personas** — pick from the 5 defaults (`novice,power,a11y,mobile,skeptic`); default is all.
- **--custom** — add your own persona; if it's vague, the plugin refines it and asks you to
  approve the line-up before running.

Example:

```
/tmp-ux:ux-review https://example.com --goal "find and start the free trial"
```

## How it works

1. The `/ux-review` command parses your request. If you didn't pass `--goal`, it **always asks you
   for the goal first** (the one required prompt). Personas default to all 5 with no prompt — unless
   you add a **custom** one, which it refines and asks you to approve before running.
2. Persona runners execute **one at a time** — they share a single Playwright browser — each
   returning a structured JSON verdict.
3. A synthesizer merges cross-persona issues, ranks them by severity × reach, and builds the
   dashboard, which is published as an Artifact.

## Requirements

- The bundled **Playwright MCP** server (`npx @playwright/mcp@latest`) — starts automatically
  when the plugin is enabled. Node.js / npx must be available on your machine.
- **Python 3** on your `PATH` (standard library only) — used to aggregate persona scores.

## Project layout

Only `agents/` and `skills/` hold content at the top level; each skill is self-contained — the
`scripts/` and `shared/` files it uses live inside its own folder, next to `SKILL.md`.

```
.claude-plugin/plugin.json   # manifest
.mcp.json                    # Playwright MCP server
agents/                      # plugin-level subagents (invoked by the skills)
  ux-persona-runner.md         # generic single-persona First-Run walkthrough executor
  ux-synthesizer.md            # semantic synthesis + dashboard builder
  ux-decay-runner.md           # one repeat-visit for the interest-decay loop
skills/
  ux-review/                       # goal-oriented First-Run evaluation (/tmp-ux:ux-review)
    SKILL.md
    scripts/aggregate.py             # deterministic score aggregation (Python, stdlib only)
    shared/default-personas.md       # the 5 default persona profiles
    shared/persona-protocol.md       # browsing protocol + output schema + scoring rubric
  ux-review-one-persona-loop/      # single-persona interest-decay loop (up to 7 visits)
    SKILL.md
    scripts/decay_slope.py           # gated least-squares decay slope (Python, stdlib only)
    shared/decay-personas.json       # persona set + config for the decay loop
```

## Interest-decay loop (`/tmp-ux:ux-review-one-persona-loop`)

A second skill measures **repeat-visit decay** for a single persona: the same persona visits the
site up to **7 times**, the browser is reset to a first-time visitor each visit, but the persona
*remembers* how often it has been — so novelty wears off like a real user. Each visit yields two decay signals and
the script leads with the trustworthy one. The **primary** signal is behavioral and observed:
`newScreens` — how many structurally-distinct screens the persona actually reaches each visit
(fingerprinted in-browser via `browser_evaluate`, then counted in Python against everything seen on
prior visits), so it falls when the site truly has nothing new whether or not the model *feels*
bored. Self-reported **interest (0–100)** is kept only as a **secondary, soft** signal — the model
was told to cool on repeat, so that curve is partly narrative. `scripts/decay_slope.py` fits a
least-squares **decay slope** to each (with standard error, R², and a noise-aware verdict). Two nested loops: outer over visits (≤ 7), inner over actions per visit.

Here the persona **leaves on its own** — the moment it leaves is the measurement, so the loop
never force-cuts a live session. Each visit records a `stopReason`: `bored`/`explored` (voluntary,
the clean signal — used for the slope), `stuck` (wandering; self-detected and cut immediately,
excluded + flagged for re-run), or `budget_cut` (a generous circuit breaker, censored). Token cost
is controlled by the wandering cut and by bored personas leaving fast in later visits — not by a
tight step ceiling, which would clip the naturally long early visits. (For deterministic,
harness-grade token control — exact DOM-hash cuts, skipping the LLM when the screen is unchanged,
per-session token caps — ② can instead be run as a standalone Python harness; ask if you want that.)

```
/tmp-ux:ux-review-one-persona-loop https://example.com --persona busy_operator --iterations 7
```

### Scoring: LLM judges, code counts

Each persona returns raw 1–5 scores (including the six **First-Run AX** dimensions). The exact
aggregation — First-Run AX Score, per-dimension averages, friction, retention — is done by
`scripts/aggregate.py` (Python standard library only), so the numbers are exact and
reproducible rather than eyeballed by the model. The model does the judgment; the script does
the arithmetic.
