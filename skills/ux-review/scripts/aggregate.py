#!/usr/bin/env python3
"""Deterministic aggregation of per-persona First-Run UX verdicts.

Usage:  python aggregate.py <verdicts.json>
  <verdicts.json> is either an array of persona verdict objects, or an object
  shaped { "url", "goal", "personas": [ ...verdicts ] }.

  To get a run-to-run RELIABILITY estimate, include the SAME persona id more than
  once (k repeated runs of that persona). Unique ids => k=1 each => no reliability
  estimate is available and the output says so.

Prints a metrics JSON to stdout. All arithmetic is computed here so the numbers are
exact and reproducible -- the LLM is never trusted to do the math.

TWO DELIBERATE CHANGES vs. a naive average
------------------------------------------
1. BEHAVIORAL vs AFFECTIVE split. The six First-Run AX dimensions are not equally
   trustworthy. Three are grounded in observed browser behavior (steps, screens,
   task completion); three are simulated *feelings*. Averaging a counted quantity
   with a vibe into one number hides that. So we report a `behavioralScore` and an
   `affectiveScore` separately (and keep a combined score only as a legacy field).

     behavioral (grounded, observed): entryBarrier, firstTaskSuccess, explorationEfficiency
     affective  (predicted feeling) : clarity, coldStart, ahaReached

2. VARIANCE, not false precision. A single run per persona is one noisy sample. We
   report the spread of scores ACROSS personas always, and the run-to-run spread
   (same persona, repeated) when it exists. If only one run per persona is given,
   `runReliability.available` is false -- the point scores are single samples.
"""

import json
import math
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

BEHAVIORAL_DIMS = ["entryBarrier", "firstTaskSuccess", "explorationEfficiency"]
AFFECTIVE_DIMS = ["clarity", "coldStart", "ahaReached"]
DIMS = BEHAVIORAL_DIMS + AFFECTIVE_DIMS

VALID_STOP = {"done", "budget_cut", "stuck"}
GATED_LOW_DIMS = ("firstTaskSuccess", "ahaReached")
BUDGET_CUT_CAP = 2


def fail(msg):
    sys.stderr.write(f"aggregate.py: {msg}\n")
    sys.exit(1)


def round1(n):
    return math.floor(n * 10 + 0.5) / 10


def mean(arr):
    return sum(arr) / len(arr) if arr else None


def sd(arr):
    """Sample standard deviation; None for fewer than 2 points."""
    if len(arr) < 2:
        return None
    m = sum(arr) / len(arr)
    return math.sqrt(sum((x - m) ** 2 for x in arr) / (len(arr) - 1))


def valid_score(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 1 <= v <= 5


def score_one_run(pid, ax, stop, warnings):
    """Return {dim: value} for a single run (budget_cut-gated), or None if incomplete."""
    dims, gated = {}, []
    complete = True
    for d in DIMS:
        v = ax.get(d)
        if not valid_score(v):
            warnings.append(f"{pid}: firstRunAX.{d} missing or out of range (got {json.dumps(v)})")
            complete = False
            continue
        if stop == "budget_cut" and d in GATED_LOW_DIMS and v > BUDGET_CUT_CAP:
            gated.append(d)
            v = BUDGET_CUT_CAP
        dims[d] = v
    if gated:
        warnings.append(f"{pid}: budget_cut -> {', '.join(gated)} capped at {BUDGET_CUT_CAP} (first-value failure, not immersion)")
    return dims if complete else None


def main():
    if len(sys.argv) < 2:
        fail("missing input file argument")

    path = sys.argv[1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        fail(f"could not read/parse {path}: {e}")

    verdicts = raw if isinstance(raw, list) else raw.get("personas")
    if not isinstance(verdicts, list) or len(verdicts) == 0:
        fail("input has no persona verdicts (expected an array or { personas: [...] })")

    warnings = []

    # Group verdicts by persona id (repeated id => repeated runs of that persona).
    groups = {}          # pid -> list of raw verdicts
    order = []
    for i, p in enumerate(verdicts):
        persona = p.get("persona") or {}
        pid = persona.get("id") or persona.get("name") or f"persona-{i + 1}"
        if pid not in groups:
            groups[pid] = []
            order.append(pid)
        groups[pid].append(p)

    stop_counts = {"done": 0, "budget_cut": 0, "stuck": 0, "unknown": 0}
    rerun_needed = []
    per_persona = []
    # Accumulators for overall dimension averages (across every included run).
    dim_values = {d: [] for d in DIMS}
    # Per-persona mean score (one number per persona) for between-persona spread.
    persona_means = []
    any_repeated = False
    run_reliability_sds = []   # per-persona SD of the score across repeated runs

    for pid in order:
        runs = groups[pid]
        run_scores = []          # this persona's per-run overall (6-dim) score
        run_beh, run_aff = [], []
        included_runs = 0
        stuck_here = 0
        for p in runs:
            ax = p.get("firstRunAX") or {}
            stop = ax.get("stopReason")
            if stop not in VALID_STOP:
                warnings.append(f"{pid}: firstRunAX.stopReason missing/invalid (got {json.dumps(stop)}); treated as 'unknown'")
                stop = "unknown"
            stop_counts[stop] += 1
            if stop == "stuck":
                stuck_here += 1
                continue
            dims = score_one_run(pid, ax, stop, warnings)
            if dims is None:
                warnings.append(f"{pid}: a run was dropped (incomplete dimensions)")
                continue
            included_runs += 1
            for d, v in dims.items():
                dim_values[d].append(v)
            run_scores.append(round1(mean([dims[d] for d in DIMS])))
            run_beh.append(round1(mean([dims[d] for d in BEHAVIORAL_DIMS])))
            run_aff.append(round1(mean([dims[d] for d in AFFECTIVE_DIMS])))

        if stuck_here and included_runs == 0:
            rerun_needed.append(pid)
            per_persona.append({"id": pid, "runs": len(runs), "includedRuns": 0,
                                "included": False, "score": None,
                                "behavioralScore": None, "affectiveScore": None})
            continue
        if included_runs == 0:
            per_persona.append({"id": pid, "runs": len(runs), "includedRuns": 0,
                                "included": False, "score": None,
                                "behavioralScore": None, "affectiveScore": None})
            continue

        score = round1(mean(run_scores))
        beh = round1(mean(run_beh))
        aff = round1(mean(run_aff))
        run_sd = sd(run_scores)
        if included_runs > 1:
            any_repeated = True
            if run_sd is not None:
                run_reliability_sds.append(run_sd)
        persona_means.append(score)
        per_persona.append({
            "id": pid,
            "runs": len(runs),
            "includedRuns": included_runs,
            "included": True,
            "score": score,
            "behavioralScore": beh,
            "affectiveScore": aff,
            "runScoreSD": (round(run_sd, 3) if run_sd is not None else None),
        })

    dimension_averages = {d: (round1(mean(dim_values[d])) if dim_values[d] else None) for d in DIMS}
    beh_avgs = [dimension_averages[d] for d in BEHAVIORAL_DIMS if dimension_averages[d] is not None]
    aff_avgs = [dimension_averages[d] for d in AFFECTIVE_DIMS if dimension_averages[d] is not None]
    behavioral_score = round1(mean(beh_avgs)) if beh_avgs else None
    affective_score = round1(mean(aff_avgs)) if aff_avgs else None
    all_avgs = [v for v in dimension_averages.values() if v is not None]
    combined_score = round1(mean(all_avgs)) if all_avgs else None

    ranked = sorted(((d, v) for d, v in dimension_averages.items() if v is not None), key=lambda kv: kv[1])
    weakest = ranked[0][0] if ranked else None
    strongest = ranked[-1][0] if ranked else None

    between_sd = sd(persona_means)
    reliability_sd = mean(run_reliability_sds) if run_reliability_sds else None

    # Honesty flags about how much to trust the point numbers.
    caution = []
    if not any_repeated:
        caution.append("Each persona ran once (k=1): no run-to-run reliability estimate. "
                       "Scores are single noisy samples; treat one-decimal precision as illustrative, not exact.")
    if between_sd is not None and between_sd >= 0.8:
        caution.append(f"Personas disagree a lot (between-persona SD {round(between_sd,2)}); "
                       "the combined score hides a wide spread.")
    if affective_score is not None and behavioral_score is not None and abs(affective_score - behavioral_score) >= 0.7:
        caution.append(f"Behavioral ({behavioral_score}) and affective ({affective_score}) scores diverge; "
                       "read them separately, not as one number.")

    # ---- Friction ----
    friction_per = []
    for pid in order:
        vals = []
        for p in groups[pid]:
            f = p.get("overallFriction")
            if isinstance(f, (int, float)) and not isinstance(f, bool) and 0 <= f <= 100:
                vals.append(f)
            else:
                warnings.append(f"{pid}: overallFriction missing or out of range (got {json.dumps(f)})")
        friction_per.append({"id": pid, "overallFriction": (round1(mean(vals)) if vals else None)})
    friction_vals = [x["overallFriction"] for x in friction_per if x["overallFriction"] is not None]
    friction_average = round1(mean(friction_vals)) if friction_vals else None

    # ---- Retention ----
    retention = {"would-stay": 0, "would-leave": 0, "unsure": 0}
    for p in verdicts:
        v = p.get("retentionVerdict")
        if v in retention:
            retention[v] += 1

    out = {
        "personaCount": len(order),
        "totalRuns": len(verdicts),
        "firstRunAX": {
            "combinedScore": combined_score,
            "behavioralScore": behavioral_score,
            "affectiveScore": affective_score,
            "scoredPersonas": len(persona_means),
            "stopReasons": stop_counts,
            "rerunNeeded": rerun_needed,
            "dimensionAverages": dimension_averages,
            "behavioralDims": BEHAVIORAL_DIMS,
            "affectiveDims": AFFECTIVE_DIMS,
            "weakestDimension": weakest,
            "strongestDimension": strongest,
            "perPersona": per_persona,
            "variance": {
                "betweenPersonaSD": (round(between_sd, 3) if between_sd is not None else None),
                "runReliability": {
                    "available": any_repeated,
                    "meanWithinPersonaSD": (round(reliability_sd, 3) if reliability_sd is not None else None),
                },
            },
        },
        "friction": {"average": friction_average, "perPersona": friction_per},
        "retention": retention,
        "caution": caution,
        "warnings": warnings,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
