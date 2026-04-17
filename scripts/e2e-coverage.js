#!/usr/bin/env node
/**
 * Convert Playwright V8 coverage JSON files to Istanbul format and generate HTML report.
 *
 * Usage: node scripts/e2e-coverage.js
 *   Reads: .coverage-e2e/*.json (V8 coverage data from Playwright tests)
 *   Writes: coverage/e2e/index.html (HTML coverage report)
 */

const fs = require("fs");
const path = require("path");
const os = require("os");
const v8toIstanbul = require("v8-to-istanbul");

const COVERAGE_DIR = path.join(__dirname, "..", ".coverage-e2e");
const OUTPUT_DIR = path.join(__dirname, "..", "coverage", "e2e");
const NYC_DIR = path.join(__dirname, "..", ".nyc_output");
const TEMP_DIR = path.join(os.tmpdir(), "e2e-coverage-temp");

async function main() {
  // Read all V8 coverage JSON files
  const coverageFiles = fs.readdirSync(COVERAGE_DIR).filter((f) => f.endsWith(".json"));

  if (coverageFiles.length === 0) {
    console.error("No coverage files found in .coverage-e2e/");
    console.error("Run tests with: COVERAGE=1 npm run test:e2e");
    process.exit(1);
  }

  console.log(`Found ${coverageFiles.length} coverage file(s)`);

  // Create temp directory for source files
  fs.mkdirSync(TEMP_DIR, { recursive: true });

  // Collect unique scripts (url -> { source, functions })
  const scripts = new Map();
  for (const file of coverageFiles) {
    const filePath = path.join(COVERAGE_DIR, file);
    const v8Coverage = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    for (const entry of v8Coverage) {
      if (!scripts.has(entry.url)) {
        scripts.set(entry.url, { source: entry.source, functions: [] });
      }
      scripts.get(entry.url).functions.push(...entry.functions);
    }
  }

  // Convert V8 coverage to Istanbul format
  const coverageMap = {};

  for (const [url, { source, functions }] of scripts) {
    // Extract file path from URL
    const pathMatch = url.match(/\/static\/js\/([^?]+)/);
    if (!pathMatch) continue; // Skip external scripts

    const filePath = path.join("vibe", "cli", "web_ui", "static", "js", pathMatch[1]);

    // Write source to temp file for v8-to-istanbul
    const tempFile = path.join(TEMP_DIR, path.basename(url));
    fs.writeFileSync(tempFile, source);

    // Convert using v8-to-istanbul (load is async)
    const script = v8toIstanbul(tempFile, 0);
    await script.load();

    if (!script.covSources || script.covSources.length === 0) {
      console.warn(`Could not load source for: ${filePath}`);
      continue;
    }

    // Apply V8 coverage blocks
    script.applyCoverage(functions);

    // Get Istanbul coverage object
    const istanbulCov = script.toIstanbul();
    for (const [key, val] of Object.entries(istanbulCov)) {
      val.path = filePath;
      coverageMap[filePath] = val;
    }
  }

  // Clean up temp files
  for (const file of fs.readdirSync(TEMP_DIR)) {
    fs.unlinkSync(path.join(TEMP_DIR, file));
  }
  fs.rmdirSync(TEMP_DIR);

  // Write Istanbul-format coverage data for debugging
  fs.mkdirSync(NYC_DIR, { recursive: true });
  const coverageFile = path.join(NYC_DIR, "coverage.json");
  fs.writeFileSync(coverageFile, JSON.stringify(coverageMap), "utf-8");

  console.log(`Wrote Istanbul coverage to ${coverageFile}`);
  console.log(`Files covered: ${Object.keys(coverageMap).length}`);

 // Print per-file stats as a table
  const rows = [];
  let totals = { stmts: 0, covered: 0, branches: 0, branchCovered: 0, funcs: 0, funcCovered: 0 };

  for (const [filePath, cov] of Object.entries(coverageMap)) {
    const stmts = Object.keys(cov.s || {});
    const covered = Object.values(cov.s || {}).filter((c) => c > 0).length;
    const branches = Object.keys(cov.b || {});
    const branchCovered = Object.values(cov.b || {}).filter((b) => b.every((v) => v > 0)).length;
    const funcs = Object.keys(cov.f || {});
    const funcCovered = Object.values(cov.f || {}).filter((c) => c > 0).length;

    totals.stmts += stmts.length;
    totals.covered += covered;
    totals.branches += branches.length;
    totals.branchCovered += branchCovered;
    totals.funcs += funcs.length;
    totals.funcCovered += funcCovered;

    rows.push({ path: filePath, covered, total: stmts.length, branchCovered, totalBranches: branches.length, funcCovered, totalFuncs: funcs.length });
  }

  // Sort by path for consistent output
  rows.sort((a, b) => a.path.localeCompare(b.path));

  const pad = (s, n) => String(s).padStart(n);
  const line = (sep = "─") => sep.repeat(78);

  console.log();
  console.log(line("─"));
  console.log(`${pad("File", 50)} ${pad("%", 6)} ${pad("Stmts", 12)} ${pad("Bran", 7)} ${pad("Func", 7)}`);
  console.log(line("─"));

  for (const { path: filePath, covered, total, branchCovered, totalBranches, funcCovered, totalFuncs } of rows) {
    const pct = total > 0 ? ((covered / total) * 100).toFixed(1) : "0.0";
    console.log(`${pad(filePath, 50)} ${pad(pct + "%", 6)} ${pad(covered + "/" + total, 12)} ${pad(branchCovered + "/" + totalBranches, 7)} ${pad(funcCovered + "/" + totalFuncs, 7)}`);
  }

  console.log(line("─"));
  const totalPct = totals.stmts > 0 ? ((totals.covered / totals.stmts) * 100).toFixed(1) : "0.0";
  console.log(`${pad("All files", 50)} ${pad(totalPct + "%", 6)} ${pad(totals.covered + "/" + totals.stmts, 12)} ${pad(totals.branchCovered + "/" + totals.branches, 7)} ${pad(totals.funcCovered + "/" + totals.funcs, 7)}`);
  console.log(line("─"));
  console.log();

  // Generate HTML report with proper directory structure using istanbul-lib-report
  const { createContext } = require("istanbul-lib-report");
  const createReport = require("istanbul-reports").create;
  const { createCoverageMap, createFileCoverage } = require("istanbul-lib-coverage");

  // Create a proper CoverageMap — must use createFileCoverage + merge
  // because addFileCoverage(path, rawCov) doesn't convert to FileCoverage
  const covMap = createCoverageMap();
  for (const [relPath, cov] of Object.entries(coverageMap)) {
    const fc = createFileCoverage(relPath);
    fc.merge(cov);
    covMap.addFileCoverage(fc);
  }

  const context = createContext({ coverageMap: covMap, dir: OUTPUT_DIR });

  createReport("html", {
    dir: OUTPUT_DIR,
    projectRoot: path.join(__dirname, ".."),
  }).execute(context);

  console.log(`\nHTML report generated: ${path.join(OUTPUT_DIR, "index.html")}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
