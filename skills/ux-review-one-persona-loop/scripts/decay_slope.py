#!/usr/bin/env python3
"""Interest-decay analysis for ONE persona's repeat-visit loop, gated by stop_reason.

Usage:  python decay_slope.py <visits.json>
  <visits.json> is shaped:
    { "id": "busy_operator", "url": "...", "goal": "...",
      "visits": [ { "visit": 1, "stopReason": "bored", "interest": 82,
                    "newScreens": 5, "turns": 6, "completed": false,
                    "summary": "..." }, ... ] }

WHY TWO SIGNALS (behavioral primary, self-report secondary)
-----------------------------------------------------------
An LLM does not actually habituate; if you *tell* it to lose interest on repeat
and then ask "how interested are you?", the reported `interest` curve is partly a
narrative it was instructed to produce. So `interest` is treated as a SECONDARY,
soft signal.

The PRIMARY signal is behavioral and observed, not felt: `newScreens` — how many
distinct new screens the persona actually found each visit. If a site truly has
nothing new on return, newScreens falls whether or not the model "feels" bored.
`turns` (actions taken before voluntarily leaving) is a TERTIARY behavioral signal
(a bored visitor leaves faster).

Each slope is reported with a standard error and R^2 so the number carries its own
uncertainty instead of pretending to be exact. The verdict leads with whether the
behavioral slope is distinguishable from noise, not with a hard-coded cutoff.

Sessions are gated by how they ended:
  bored / explored -> clean voluntary exit; USED for the slopes (the real signal)
  stuck            -> wandering/malfunction; EXCLUDED and flagged for re-run
  budget_cut       -> hit the circuit breaker; CENSORED (a lower bound), not in slopes

All arithmetic lives here so the numbers are exact and reproducible.
"""

import json
import math
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

VALID_STOP = {"bored", "explored", "stuck", "budget_cut"}
CLEAN = {"bored", "explored"}  # only these count toward the slopes


def fail(msg):
    sys.stderr.write(f"decay_slope.py: {msg}\n")
    sys.exit(1)


def regress(xs, ys):
    """Least-squares regression of ys on xs.

    Returns slope, standard error of the slope (None if fewer than 3 points, i.e.
    zero residual degrees of freedom), and R^2 (None if <3 points or no variance).
    """
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return {"slope": 0.0, "stdErr": None, "r2": None, "n": n}
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    sse = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    sst = sum((y - my) ** 2 for y in ys)
    r2 = (1 - sse / sst) if (n >= 3 and sst > 0) else None
    # Standard error of the slope needs residual df = n - 2 >= 1, i.e. n >= 3.
    std_err = math.sqrt((sse / (n - 2)) / sxx) if n >= 3 else None
    return {
        "slope": round(slope, 3),
        "stdErr": (round(std_err, 3) if std_err is not None else None),
        "r2": (round(r2, 3) if r2 is not None else None),
        "n": n,
    }


def significance(fit):
    """Classify a slope against its own noise, not an arbitrary cutoff.

    Uses a ~1 standard-error band (low statistical power is unavoidable with a
    handful of visits, so this is deliberately a weak, honest test)."""
    s, se, n = fit["slope"], fit["stdErr"], fit["n"]
    if n < 2:
        return "inconclusive"
    if se is None:            # exactly 2 points: slope exists, uncertainty doesn't
        return "unpowered"
    if se == 0:
        return "declining" if s < 0 else ("rising" if s > 0 else "flat")
    if s + se < 0:
        return "declining"
    if s - se > 0:
        return "rising"
    return "flat"             # within one SE of zero -> indistinguishable from noise


def behavioral_verdict(sig, fit):
    s = fit["slope"]
    if sig == "declining":
        strength = "steep" if s <= -1.0 else "gentle"
        return (f"{strength} behavioral decay -- distinct new screens per revisit actually fall "
                "off (observed, not self-reported)")
    if sig == "rising":
        return "new screens increase on each revisit -- there is still something to discover"
    if sig == "flat":
        return ("no behavioral decay signal -- the change in new-screen count is indistinguishable "
                "from noise (uncertain)")
    if sig == "unpowered":
        return ("only 2 clean sessions -- a slope exists but its uncertainty cannot be estimated; "
                "treat as weak evidence")
    return "behavioral slope not computable -- fewer than 2 clean (bored/explored) sessions"


def interest_note(sig, fit):
    if fit["n"] < 2:
        return "self-reported interest slope not computable (fewer than 2 clean sessions)"
    s = fit["slope"]
    tag = {"declining": "down", "rising": "up", "flat": "flat (noise level)",
           "unpowered": "uncertain (2 points)"}[sig]
    return (f"self-reported interest slope {s} ({tag}) -- SECONDARY signal only. The model was "
            "instructed to lose interest on repeat, so this partly reflects that narrative; "
            "cross-check it against the behavioral signal.")


def valid_num(v, lo, hi):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi


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
    series = []
    clean_interest = []     # (visit, interest)   secondary
    clean_screens = []      # (visit, newScreens) PRIMARY behavioral
    clean_turns = []        # (visit, turns)      tertiary behavioral
    rerun_needed = []
    censored = []
    completed_count = 0

    for i, v in enumerate(visits, 1):
        stop = v.get("stopReason")
        if stop not in VALID_STOP:
            warnings.append(f"visit {i}: stopReason missing/invalid (got {json.dumps(stop)}); treated as 'unknown'")
            stop = "unknown"
        stop_counts[stop] += 1

        iv = v.get("interest")
        ivv = iv if valid_num(iv, 0, 100) else None
        ns = v.get("newScreens")
        nsv = ns if valid_num(ns, 0, 10000) else None
        tn = v.get("turns")
        tnv = tn if valid_num(tn, 0, 10000) else None
        if ivv is None:
            warnings.append(f"visit {i}: interest missing or out of range (got {json.dumps(iv)})")
        if nsv is None:
            warnings.append(f"visit {i}: newScreens missing or out of range (got {json.dumps(ns)})")

        series.append({"visit": i, "interest": ivv, "newScreens": nsv,
                       "turns": tnv, "stopReason": stop})

        if v.get("completed") is True:
            completed_count += 1

        if stop == "stuck":
            rerun_needed.append(i)
        elif stop == "budget_cut":
            censored.append(i)
        elif stop in CLEAN:
            if ivv is not None:
                clean_interest.append((i, ivv))
            if nsv is not None:
                clean_screens.append((i, nsv))
            if tnv is not None:
                clean_turns.append((i, tnv))

    def build(points):
        if len(points) < 2:
            return {"slope": None, "stdErr": None, "r2": None, "n": len(points),
                    "significance": "inconclusive",
                    "first": (points[0][1] if points else None),
                    "last": (points[-1][1] if points else None)}
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        fit = regress(xs, ys)
        fit["significance"] = significance(fit)
        fit["first"] = ys[0]
        fit["last"] = ys[-1]
        return fit

    primary = build(clean_screens)      # newScreens — behavioral, PRIMARY
    secondary = build(clean_interest)   # interest   — self-report, SECONDARY
    tertiary = build(clean_turns)       # turns      — behavioral, TERTIARY

    if primary["n"] < 2:
        warnings.append("fewer than 2 clean (bored/explored) sessions with newScreens; "
                        "behavioral slope not computed — run is inconclusive")

    out = {
        "id": data.get("id"),
        "url": data.get("url"),
        "goal": data.get("goal"),
        "visits": len(visits),
        "stopReasons": stop_counts,
        "cleanSessions": len(clean_screens) if clean_screens else len(clean_interest),
        "rerunNeeded": rerun_needed,
        "censored": censored,
        "completedCount": completed_count,
        "series": series,
        "primaryBehavioral": {
            "metric": "newScreens (distinct new screens per visit)",
            **primary,
            "verdict": behavioral_verdict(primary.get("significance", "inconclusive"), primary),
        },
        "secondarySelfReport": {
            "metric": "interest (0-100 self-reported)",
            **secondary,
            "note": interest_note(secondary.get("significance", "inconclusive"), secondary),
        },
        "tertiaryBehavioral": {
            "metric": "turns (actions before voluntary exit)",
            **tertiary,
        },
        "warnings": warnings,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
