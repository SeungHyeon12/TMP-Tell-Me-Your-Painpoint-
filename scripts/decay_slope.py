#!/usr/bin/env python3
"""Interest-decay slope for ONE persona's repeat-visit loop.

Usage:  python decay_slope.py <visits.json>
  <visits.json> is shaped:
    { "id": "busy_operator", "url": "...", "goal": "...",
      "visits": [ { "visit": 1, "interest": 82, "completed": false, "turns": 3,
                    "summary": "..." }, ... ] }

Prints a metrics JSON to stdout. The least-squares slope of interest over the visit
axis is the "how fast this cold-start gets stale on repeat exposure" number. Negative
slope = decay. All arithmetic lives here so the number is exact and reproducible.

Mirrors the slope() / verdict() logic of the original interest_decay_loop.py.
"""

import json
import statistics
import sys

# Force UTF-8 stdout so Korean output survives Windows' default cp949 console.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def fail(msg):
    sys.stderr.write(f"decay_slope.py: {msg}\n")
    sys.exit(1)


def slope(ys):
    """Least-squares slope of interest vs visit index (1,2,3...). Negative = decay."""
    n = len(ys)
    xs = list(range(1, n + 1))
    mx, my = statistics.mean(xs), statistics.mean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def verdict(s):
    if s < -3:
        return "가파른 감쇠 — 콜드스타트가 반복 노출에 빠르게 질림"
    if s < -1:
        return "완만한 감쇠 — novelty가 식지만 급하진 않음"
    return "흥미 유지 — 반복 노출에도 신선도가 버팀"


def valid_interest(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 100


def main():
    if len(sys.argv) < 2:
        fail("missing input file argument")
    try:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        fail(f"could not read/parse {sys.argv[1]}: {e}")

    visits = data.get("visits")
    if not isinstance(visits, list) or len(visits) == 0:
        fail("input needs a non-empty 'visits' list")

    warnings = []
    if len(visits) > 7:
        warnings.append(f"received {len(visits)} visits; this loop is capped at 7")

    interests, completed_count = [], 0
    for i, v in enumerate(visits, 1):
        iv = v.get("interest")
        if valid_interest(iv):
            interests.append(iv)
        else:
            warnings.append(f"visit {i}: interest missing or out of range (got {json.dumps(iv)})")
        if v.get("completed") is True:
            completed_count += 1

    if not interests:
        fail("no valid interest scores to compute a slope")

    s = slope(interests)

    out = {
        "id": data.get("id"),
        "url": data.get("url"),
        "goal": data.get("goal"),
        "n": len(interests),
        "interests": interests,
        "firstInterest": interests[0],
        "lastInterest": interests[-1],
        "drop": interests[0] - interests[-1],
        "slope": round(s, 3),
        "verdict": verdict(s),
        "completedCount": completed_count,
        "warnings": warnings,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
