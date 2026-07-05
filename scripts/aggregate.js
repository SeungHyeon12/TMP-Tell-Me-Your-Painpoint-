#!/usr/bin/env node
/*
 * Deterministic aggregation of per-persona UX verdicts.
 *
 * Usage:  node aggregate.js <verdicts.json>
 *   <verdicts.json> is either an array of persona verdict objects, or
 *   an object shaped { url, mode, personas: [ ...verdicts ] }.
 *
 * Prints a metrics JSON to stdout. All arithmetic (First-Run AX Score,
 * per-dimension averages, friction, retention counts) is computed here so the
 * numbers are exact and reproducible — the LLM is never trusted to do the math.
 */

const fs = require("fs");

const DIMS = [
  "clarity",
  "coldStart",
  "entryBarrier",
  "firstTaskSuccess",
  "ahaReached",
  "nextAction",
];

function fail(msg) {
  console.error(`aggregate.js: ${msg}`);
  process.exit(1);
}

const file = process.argv[2];
if (!file) fail("missing input file argument");

let raw;
try {
  raw = JSON.parse(fs.readFileSync(file, "utf8"));
} catch (e) {
  fail(`could not read/parse ${file}: ${e.message}`);
}

const personas = Array.isArray(raw) ? raw : raw.personas;
if (!Array.isArray(personas) || personas.length === 0) {
  fail("input has no persona verdicts (expected an array or { personas: [...] })");
}

const round1 = (n) => Math.round(n * 10) / 10;
const mean = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null);

// A valid rubric score is an integer-ish number in [1,5].
function validScore(v) {
  return typeof v === "number" && isFinite(v) && v >= 1 && v <= 5;
}

const warnings = [];

// ---- First-Run AX -------------------------------------------------------
const perPersonaAX = [];
const dimValues = Object.fromEntries(DIMS.map((d) => [d, []]));

personas.forEach((p, i) => {
  const id = (p.persona && (p.persona.id || p.persona.name)) || `persona-${i + 1}`;
  const ax = p.firstRunAX || {};
  const dims = {};
  const collected = [];
  for (const d of DIMS) {
    const v = ax[d];
    if (validScore(v)) {
      dims[d] = v;
      dimValues[d].push(v);
      collected.push(v);
    } else {
      warnings.push(`${id}: firstRunAX.${d} missing or out of range (got ${JSON.stringify(v)})`);
    }
  }
  // Recompute the persona score from the dimensions — authoritative, ignores any
  // score the LLM wrote.
  const score = collected.length === DIMS.length ? round1(mean(collected)) : null;
  if (score === null) warnings.push(`${id}: First-Run AX score not computed (incomplete dimensions)`);
  perPersonaAX.push({ id, dims, score });
});

const dimensionAverages = {};
for (const d of DIMS) dimensionAverages[d] = dimValues[d].length ? round1(mean(dimValues[d])) : null;

const personaScores = perPersonaAX.map((p) => p.score).filter((s) => s !== null);
const overallScore = personaScores.length ? round1(mean(personaScores)) : null;

const ranked = Object.entries(dimensionAverages).filter(([, v]) => v !== null).sort((a, b) => a[1] - b[1]);
const weakestDimension = ranked.length ? ranked[0][0] : null;
const strongestDimension = ranked.length ? ranked[ranked.length - 1][0] : null;

// ---- Friction -----------------------------------------------------------
const frictionPer = personas.map((p, i) => {
  const id = (p.persona && (p.persona.id || p.persona.name)) || `persona-${i + 1}`;
  const f = p.overallFriction;
  const valid = typeof f === "number" && isFinite(f) && f >= 0 && f <= 100;
  if (!valid) warnings.push(`${id}: overallFriction missing or out of range (got ${JSON.stringify(f)})`);
  return { id, overallFriction: valid ? f : null };
});
const frictionVals = frictionPer.map((x) => x.overallFriction).filter((x) => x !== null);
const frictionAverage = frictionVals.length ? round1(mean(frictionVals)) : null;

// ---- Retention ----------------------------------------------------------
const retention = { "would-stay": 0, "would-leave": 0, unsure: 0 };
personas.forEach((p) => {
  const v = p.retentionVerdict;
  if (v in retention) retention[v] += 1;
});

const out = {
  personaCount: personas.length,
  firstRunAX: {
    overallScore,
    dimensionAverages,
    weakestDimension,
    strongestDimension,
    perPersona: perPersonaAX.map(({ id, score }) => ({ id, score })),
  },
  friction: { average: frictionAverage, perPersona: frictionPer },
  retention,
  warnings,
};

process.stdout.write(JSON.stringify(out, null, 2) + "\n");
