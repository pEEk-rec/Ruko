// Bundle budget check: run after `npm run build`. Prints the gzipped size of every built file
// and fails if the first download (the entry script plus the CSS) goes over the budget.
// The charts and the broker demo are separate lazy chunks and are not part of the first download.

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const BUDGET_KB = { entryJs: 100, css: 10 };
const dir = new URL("../dist/assets/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

const files = readdirSync(dir).map((name) => ({
  name,
  kb: gzipSync(readFileSync(join(dir, name))).length / 1024,
}));
files.forEach((f) => console.log(`${f.kb.toFixed(1).padStart(7)} KB gzip  ${f.name}`));

const lazy = /^(ScenarioChart|BrokerApp)-/;
const entry = files.find((f) => f.name.endsWith(".js") && !lazy.test(f.name));
const css = files.find((f) => f.name.endsWith(".css"));
const problems = [];
if (!entry || entry.kb > BUDGET_KB.entryJs) problems.push(`entry JS over ${BUDGET_KB.entryJs} KB gzip`);
if (!css || css.kb > BUDGET_KB.css) problems.push(`CSS over ${BUDGET_KB.css} KB gzip`);
if (!files.some((f) => f.name.startsWith("ScenarioChart-"))) problems.push("charts are not a lazy chunk");
if (!files.some((f) => f.name.startsWith("BrokerApp-"))) problems.push("broker demo is not a lazy chunk");

if (problems.length > 0) {
  console.error(`Bundle budget failed: ${problems.join("; ")}`);
  process.exit(1);
}
console.log("Bundle budget ok (first download: entry JS + CSS).");
