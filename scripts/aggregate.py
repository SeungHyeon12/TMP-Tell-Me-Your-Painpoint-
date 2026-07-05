#!/usr/bin/env python3
"""Deterministic aggregation of per-persona UX verdicts.

Usage:  python aggregate.py <verdicts.json>
  <verdicts.json> is either an array of persona verdict objects, or an object
  shaped { "url", "goal", "personas": [ ...verdicts ] }.

Prints a metrics JSON to stdout. All arithmetic (First-Run AX Score, per-dimension
averages, friction, retention counts) is computed here so the numbers are exact and
reproducible -- the LLM is never trusted to do the math.
"""

import json
import math
import sys

# Force UTF-8 stdout so non-ASCII (e.g. Korean persona ids) survive Windows' cp949 console.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

DIMS = [
    "clarity",
    "coldStart",
    "entryBarrier",
    "firstTaskSuccess",
    "ahaReached",
    "nextAction",
]


def fail(msg):
    sys.stderr.write(f"aggregate.py: {msg}\n")
    sys.exit(1)


def round1(n):
    # Round half up (3.25 -> 3.3), not Python's default banker's rounding.
    return math.floor(n * 10 + 0.5) / 10


def mean(arr):
    return sum(arr) / len(arr) if arr else None


def valid_score(v):
    """A valid rubric score is a number in [1, 5]."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 1 <= v <= 5


def main():
    if len(sys.argv) < 2:
        fail("missing input file argument")

    path = sys.argv[1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        fail(f"could not read/parse {path}: {e}")

    personas = raw if isinstance(raw, list) else raw.get("personas")
    if not isinstance(personas, list) or len(personas) == 0:
        fail("input has no persona verdicts (expected an array or { personas: [...] })")

    warnings = []

    # ---- First-Run AX ---------------------------------------------------
    per_persona_ax = []
    dim_values = {d: [] for d in DIMS}

    for i, p in enumerate(personas):
        persona = p.get("persona") or {}
        pid = persona.get("id") or persona.get("name") or f"persona-{i + 1}"
        ax = p.get("firstRunAX") or {}
        collected = []
        for d in DIMS:
            v = ax.get(d)
            if valid_score(v):
                dim_values[d].append(v)
                collected.append(v)
            else:
                warnings.append(
                    f"{pid}: firstRunAX.{d} missing or out of range (got {json.dumps(v)})"
                )
        # Recompute the persona score from the dimensions -- authoritative, ignores
        # any score the LLM wrote.
        if len(collected) == len(DIMS):
            score = round1(mean(collected))
        else:
            score = None
            warnings.append(f"{pid}: First-Run AX score not computed (incomplete dimensions)")
        per_persona_ax.append({"id": pid, "score": score})

    dimension_averages = {
        d: (round1(mean(dim_values[d])) if dim_values[d] else None) for d in DIMS
    }

    persona_scores = [p["score"] for p in per_persona_ax if p["score"] is not None]
    overall_score = round1(mean(persona_scores)) if persona_scores else None

    ranked = sorted(
        ((d, v) for d, v in dimension_averages.items() if v is not None),
        key=lambda kv: kv[1],
    )
    weakest_dimension = ranked[0][0] if ranked else None
    strongest_dimension = ranked[-1][0] if ranked else None

    # ---- Friction -------------------------------------------------------
    friction_per = []
    for i, p in enumerate(personas):
        persona = p.get("persona") or {}
        pid = persona.get("id") or persona.get("name") or f"persona-{i + 1}"
        f = p.get("overallFriction")
        is_valid = isinstance(f, (int, float)) and not isinstance(f, bool) and 0 <= f <= 100
        if not is_valid:
            warnings.append(f"{pid}: overallFriction missing or out of range (got {json.dumps(f)})")
        friction_per.append({"id": pid, "overallFriction": f if is_valid else None})

    friction_vals = [x["overallFriction"] for x in friction_per if x["overallFriction"] is not None]
    friction_average = round1(mean(friction_vals)) if friction_vals else None

    # ---- Retention ------------------------------------------------------
    retention = {"would-stay": 0, "would-leave": 0, "unsure": 0}
    for p in personas:
        v = p.get("retentionVerdict")
        if v in retention:
            retention[v] += 1

    out = {
        "personaCount": len(personas),
        "firstRunAX": {
            "overallScore": overall_score,
            "dimensionAverages": dimension_averages,
            "weakestDimension": weakest_dimension,
            "strongestDimension": strongest_dimension,
            "perPersona": per_persona_ax,
        },
        "friction": {"average": friction_average, "perPersona": friction_per},
        "retention": retention,
        "warnings": warnings,
    }

    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
