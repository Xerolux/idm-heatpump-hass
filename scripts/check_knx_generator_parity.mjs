#!/usr/bin/env node
/* Parity harness: the website's KNX generator (knx-generator-core.mjs) must
   produce exactly what scripts/generate_knx_group_addresses.py produces.
   Runs both for a set of fixture configurations and compares XML and CSV
   byte for byte; invalid base addresses must be rejected by both.
   Exits nonzero on the first mismatch. */

import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import * as path from "node:path";
import * as url from "node:url";

const here = path.dirname(url.fileURLToPath(import.meta.url));
const args = process.argv.slice(2);

function readOption(name, fallback) {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : fallback;
}

const corePath = readOption("--core", path.join(here, "..", "docs", "public", "docs", "knx-generator-core.mjs"));
const catalogPath = readOption("--catalog");
const pythonBin = readOption("--python", process.env.PYTHON || "python");
const generatorPath = readOption("--generator", path.join(here, "generate_knx_group_addresses.py"));

if (!catalogPath) {
  console.error("usage: check_knx_generator_parity.mjs --catalog <knx-catalog.json> [--python <bin>] [--core <mjs>] [--generator <py>]");
  process.exit(2);
}

const core = await import(url.pathToFileURL(corePath).href);
const catalog = JSON.parse(readFileSync(catalogPath, "utf8"));
const groupLabels = Object.fromEntries(catalog.groups.map((group) => [group.id, group.label]));

const fixtures = [
  { name: "full @ 8/0/0", base: "8/0/0", selection: {} },
  { name: "compact @ 11/0/0", base: "11/0/0", selection: { preset: "compact" } },
  { name: "groups system,dhw,energy @ 8/0/0", base: "8/0/0", selection: { groups: ["system", "dhw", "energy"] } },
  { name: "groups heating_circuits @ 5/5/5", base: "5/5/5", selection: { groups: ["heating_circuits"] } },
  { name: "groups zones @ 0/0/1", base: "0/0/1", selection: { groups: ["zones"] } },
];

const invalidBases = ["8/0/256", "32/0/0", "65536", "", "  ", "a/b/c", "-1", "0/0/0", "1/2/3/4", "31/7/0"];

function pythonOutput(base, selection, format) {
  const cliArgs = ["--base", base, "--format", format, "--stdout"];
  if (selection.preset === "compact") {
    cliArgs.push("--profile", "compact");
  }
  if (selection.groups) {
    cliArgs.push("--groups", selection.groups.join(","));
  }
  const result = spawnSync(pythonBin, [generatorPath, ...cliArgs], {
    encoding: "utf8",
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  });
  return result;
}

function firstDifference(actual, expected) {
  const actualLines = actual.split("\n");
  const expectedLines = expected.split("\n");
  const limit = Math.max(actualLines.length, expectedLines.length);
  for (let index = 0; index < limit; index += 1) {
    if (actualLines[index] !== expectedLines[index]) {
      return { line: index + 1, actual: actualLines[index], expected: expectedLines[index] };
  }
  }
  return null;
}

let failures = 0;

for (const fixture of fixtures) {
  const objects = core.selectObjects(catalog, fixture.selection);
  const rows = core.buildRows(catalog, fixture.base, objects);
  const jsXml = core.renderXml(rows, { groupLabels });
  const jsCsv = core.renderCsv(rows, { groupLabels });

  for (const [format, actual] of [
    ["xml", jsXml],
    ["csv", jsCsv],
  ]) {
    const result = pythonOutput(fixture.base, fixture.selection, format);
    if (result.status !== 0) {
      console.error(`FAIL ${fixture.name} (${format}): python generator exited ${result.status}`);
      failures += 1;
      continue;
    }
    const expected = result.stdout.replace(/\r\n/g, "\n");
    if (actual !== expected) {
      const difference = firstDifference(actual, expected);
      console.error(`FAIL ${fixture.name} (${format}) first difference at line ${difference.line}:`);
      console.error(`  core.mjs: ${JSON.stringify(difference.actual)}`);
      console.error(`  python:   ${JSON.stringify(difference.expected)}`);
      failures += 1;
    }
  }
}

for (const base of invalidBases) {
  const pythonResult = pythonOutput(base, {}, "xml");
  let jsRejected = false;
  try {
    const objects = core.selectObjects(catalog, {});
    core.buildRows(catalog, base, objects);
  } catch {
    jsRejected = true;
  }
  if (pythonResult.status === 0) {
    console.error(`FAIL invalid base ${JSON.stringify(base)}: python generator accepted it`);
    failures += 1;
  } else if (!jsRejected) {
    console.error(`FAIL invalid base ${JSON.stringify(base)}: core.mjs accepted it`);
    failures += 1;
  }
}

if (failures) {
  console.error(`${failures} parity failure(s)`);
  process.exit(1);
}
console.log(`parity ok: ${fixtures.length} fixture(s) byte-identical, ${invalidBases.length} invalid base(s) rejected by both`);
