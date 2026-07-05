# Decay-slope validation (known-answer test)

This closes the "no ground truth" gap for the interest-decay loop. It checks that the
**behavioral decay slope** (`primaryBehavioral`, the DOM-fingerprinted `newScreens` slope) actually
*discriminates* a site that goes stale from one that stays fresh — not that it always reports decay.

The two fixtures differ in **one variable only** (novelty on repeat), so any slope difference is
attributable to that, not to persona/goal/loading confounds.

| Fixture | What it does on each visit | Ground truth (behavioral slope) |
|---|---|---|
| `static.html` | Byte-identical every load | **declining** — nothing new on return |
| `fresh.html`  | A genuinely different tip each load (distinct fingerprint) | **flat / rising** — novelty renews |

## Run it

Point the loop at each fixture as a `file://` URL, same persona (`curious_explorer`), same goal,
`--iterations 7`:

```
/tmp-ux:ux-review-one-persona-loop file:///ABS/PATH/validation/static.html --persona curious_explorer --iterations 7
/tmp-ux:ux-review-one-persona-loop file:///ABS/PATH/validation/fresh.html  --persona curious_explorer --iterations 7
```

Replace `/ABS/PATH/` with this repo's absolute path. For a **reliability** read, run each fixture
3 times and look at the run-to-run spread of the slope.

## Pass gate (pre-registered — decide before running)

Read `primaryBehavioral` (behavioral, DOM-fingerprinted) from `decay_slope.py`, not the self-report:

- **G-discriminate (core):** `slope(static) < slope(fresh)`, i.e. static is clearly more negative.
  This is the whole test — if the two don't separate, the slope isn't measuring novelty (it's a
  scripted "I've seen it before" prior). ❌ FAIL if they overlap.
- **G-direction:** `static` classifies as `declining`; `fresh` classifies as `flat` or `rising`.
- **G-noise:** across the 3 reliability runs, the sign of each fixture's slope is stable.
- **G-source:** every visit's `newScreensSource` is `dom-fingerprint` (not `self-report`) — otherwise
  you validated the soft signal, not the objective one. Check the `warnings` array is clear of the
  fingerprint-fallback note.

Passing G-discriminate + G-direction is the honest claim to make: *the behavioral decay slope
distinguishes a stale experience from a fresh one.* It does not prove calibrated magnitudes — that
needs real-user retention data — but it rules out the failure mode the research literature flags
(synthetic users reporting rigid, content-independent decay).
