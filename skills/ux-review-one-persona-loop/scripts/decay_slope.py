#!/usr/bin/env python3
"""Interest-decay slope for ONE persona's repeat-visit loop, gated by stop_reason.

Usage:  python decay_slope.py <visits.json>
  <visits.json> is shaped:
    { "id": "busy_operator", "url": "...", "goal": "...",
      "visits": [ { "visit": 1, "stopReason": "bored", "interest": 82,
                    "completed": false, "turns": 3, "summary": "..." }, ... ] }

The decay slope is the least-squares slope of interest over the visit axis (negative =
interest fades on repeat). Sessions are gated by how they ended:

  bored / explored -> clean voluntary exit; USED for the slope (the real signal)
  stuck            -> wandering/malfunction; EXCLUDED and flagged for re-run
  budget_cut       -> hit the circuit breaker; CENSORED (a lower bound only), not in the slope

All arithmetic lives here so the number is exact and reproducible.
"""

import json
import statistics
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

VALID_STOP = {"bored", "explored", "stuck", "budget_cut"}
CLEAN = {"bored", "explored"}  # only these count toward the decay slope


def fail(msg):
    sys.stderr.write(f"decay_slope.py: {msg}\n")
    sys.exit(1)


def slope_xy(xs, ys):
    """Least-squares slope of ys over xs (visit indices, not necessarily contiguous)."""
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

    stop_counts = {"bored": 0, "explored": 0, "stuck": 0, "budget_cut": 0, "unknown": 0}
    series = []            # every visit, annotated, for display
    clean_pts = []         # (visitIndex, interest) for bored/explored only
    rerun_needed = []      # stuck visit indices
    censored = []          # budget_cut visit indices
    completed_count = 0

    for i, v in enumerate(visits, 1):
        stop = v.get("stopReason")
        if stop not in VALID_STOP:
            warnings.append(f"visit {i}: stopReason missing/invalid (got {json.dumps(stop)}); treated as 'unknown'")
            stop = "unknown"
        stop_counts[stop] += 1

        iv = v.get("interest")
        ivv = iv if valid_interest(iv) else None
        if ivv is None:
            warnings.append(f"visit {i}: interest missing or out of range (got {json.dumps(iv)})")
        series.append({"visit": i, "interest": ivv, "stopReason": stop})

        if v.get("completed") is True:
            completed_count += 1

        if stop == "stuck":
            rerun_needed.append(i)          # excluded from the slope, re-run
        elif stop == "budget_cut":
            censored.append(i)              # censored lower bound, not in the slope
        elif stop in CLEAN and ivv is not None:
            clean_pts.append((i, ivv))      # the clean signal

    # Slope from clean (bored/explored) sessions only.
    if len(clean_pts) >= 2:
        xs = [x for x, _ in clean_pts]
        ys = [y for _, y in clean_pts]
        s = round(slope_xy(xs, ys), 3)
        v_text = verdict(s)
        first_interest, last_interest = ys[0], ys[-1]
        drop = first_interest - last_interest
    else:
        s = None
        v_text = "감쇠 기울기 계산 불가 — 자발 종료(bored/explored) 세션이 2개 미만 (재실행 또는 방문 수 확대 필요)"
        first_interest = last_interest = drop = None
        warnings.append("fewer than 2 clean (bored/explored) sessions; slope not computed")

    out = {
        "id": data.get("id"),
        "url": data.get("url"),
        "goal": data.get("goal"),
        "visits": len(visits),
        "stopReasons": stop_counts,
        "cleanSessions": len(clean_pts),
        "rerunNeeded": rerun_needed,
        "censored": censored,
        "series": series,
        "slopeInterests": [y for _, y in clean_pts],
        "slope": s,
        "verdict": v_text,
        "firstInterest": first_interest,
        "lastInterest": last_interest,
        "drop": drop,
        "completedCount": completed_count,
        "warnings": warnings,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
