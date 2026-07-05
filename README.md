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
/tmp-ux:ux-review <url> [--mode freeroam|task] [--task "goal"] [--personas ...] [--custom "..."]
```

- **freeroam** — personas explore with no goal and report general impressions & friction.
- **task** — personas attempt a concrete goal (e.g. "complete signup") and report where they
  get stuck (Cognitive Walkthrough).
- **--personas** — pick from the 5 defaults (`novice,power,a11y,mobile,skeptic`); default is all.
- **--custom** — add your own persona; if it's vague, the plugin refines it and asks you to
  approve the line-up before running.

Example:

```
/tmp-ux:ux-review https://example.com --mode task --task "find and start the free trial"
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

## Project layout

```
.claude-plugin/plugin.json   # manifest
.mcp.json                    # Playwright MCP server
skills/ux-review/SKILL.md    # orchestrator skill (auto-invocable + /tmp-ux:ux-review)
agents/
  ux-persona-runner.md       # generic single-persona walkthrough executor
  ux-synthesizer.md          # aggregation + dashboard builder
shared/
  default-personas.md        # the 5 default persona profiles
  persona-protocol.md        # browsing protocol + output schema + scoring rubric
```
