#!/usr/bin/env node
/**
 * Scans src TSX files (excluding test/) for button elements and reports
 * tooltip coverage via ToolTip wrappers or tipId props on components.
 */
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const webRoot = join(__dirname, "..");
const srcRoot = join(webRoot, "src");
const outPath = join(srcRoot, "lib", "tooltipManifest.json");

const BUTTON_RE = /<button\b/g;
const TOOLTIP_WRAP_RE = /<ToolTip\b[^>]*\bid=\{?["']([^"'}]+)["']\}?/g;
const TIP_ID_PROP_RE = /\btipId=\{?["']([^"'}]+)["']\}?/g;

/** Meta tooltip UI — buttons are not product controls. */
const ALLOWLIST_FILES = new Set([
  "src/components/ToolTipDock.tsx",
  "src/components/ToolTipDetail.tsx",
]);

/**
 * Wrapper components whose internal <button> is covered when tipId is passed
 * at the call site (or when the component wraps with ToolTip when tipId is set).
 */
const TIP_ID_WRAPPER_COMPONENTS = [
  "DeleteButton",
  "StashButton",
  "PanelToggle",
  "TargetLengthInput",
  "EditorSaveBar",
];

/** Inner RunButton/MineButton definitions in ChapterWorkflowToolbar. */
const WORKFLOW_INNER_BUTTON_FNS = new Set(["RunButton", "MineButton", "ToggleChip"]);

function walkTsx(dir, files = []) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const rel = relative(srcRoot, full);
    if (rel.startsWith("test" + "/") || rel.includes("/test/")) continue;
    const st = statSync(full);
    if (st.isDirectory()) walkTsx(full, files);
    else if (name.endsWith(".tsx")) files.push(full);
  }
  return files;
}

function lineOf(text, index) {
  return text.slice(0, index).split("\n").length;
}

function snippetAt(text, index) {
  const start = Math.max(0, text.lastIndexOf("\n", index) + 1);
  const end = text.indexOf("\n", index);
  return text.slice(start, end === -1 ? undefined : end).trim().slice(0, 120);
}

function collectTipIds(text) {
  const ids = new Set();
  for (const re of [TOOLTIP_WRAP_RE, TIP_ID_PROP_RE]) {
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(text))) ids.add(m[1]);
  }
  return [...ids];
}

function enclosingFunctionName(text, buttonIndex) {
  const before = text.slice(0, buttonIndex);
  const matches = [...before.matchAll(/function\s+(\w+)\s*\(/g)];
  return matches.length ? matches[matches.length - 1][1] : null;
}

function isWorkflowInnerButton(text, buttonIndex, fileRel) {
  if (fileRel !== "src/components/ChapterWorkflowToolbar.tsx") return false;
  const fn = enclosingFunctionName(text, buttonIndex);
  return fn != null && WORKFLOW_INNER_BUTTON_FNS.has(fn);
}

function isPrimitiveInternalButton(text, buttonIndex, fileRel) {
  const base = fileRel.replace(/^src\/components\//, "");
  if (
    base === "DeleteButton.tsx" ||
    base === "StashButton.tsx" ||
    base === "PanelToggle.tsx" ||
    base === "TargetLengthInput.tsx"
  ) {
    return true;
  }
  if (fileRel === "src/components/ManuscriptControls.tsx") {
    return enclosingFunctionName(text, buttonIndex) === "ToggleChip";
  }
  return isWorkflowInnerButton(text, buttonIndex, fileRel);
}

function countWrapperUsagesWithTipId(allTexts) {
  const counts = Object.fromEntries(TIP_ID_WRAPPER_COMPONENTS.map((n) => [n, 0]));
  const usageRe = new RegExp(
    `<(${TIP_ID_WRAPPER_COMPONENTS.join("|")})\\b[\\s\\S]*?\\btipId=`,
    "g",
  );
  for (const text of allTexts) {
    usageRe.lastIndex = 0;
    let m;
    while ((m = usageRe.exec(text))) {
      counts[m[1]] = (counts[m[1]] ?? 0) + 1;
    }
  }
  return counts;
}

function hasNearbyToolTip(text, buttonIndex) {
  const windowStart = Math.max(0, buttonIndex - 600);
  const windowEnd = Math.min(text.length, buttonIndex + 200);
  const slice = text.slice(windowStart, windowEnd);
  if (/<ToolTip\b/.test(slice)) return true;
  if (/\btipId=/.test(slice)) return true;
  return false;
}

function isPanelToggleInsideToolTip(text, buttonIndex) {
  const windowStart = Math.max(0, buttonIndex - 1200);
  const slice = text.slice(windowStart, buttonIndex);
  const opens = (slice.match(/<ToolTip\b/g) ?? []).length;
  const closes = (slice.match(/<\/ToolTip>/g) ?? []).length;
  return opens > closes;
}

const files = walkTsx(srcRoot);
const allTexts = files.map((f) => readFileSync(f, "utf8"));
const wrapperTipIdCounts = countWrapperUsagesWithTipId(allTexts);

const buttons = [];
const tipIdsByFile = {};

for (let i = 0; i < files.length; i++) {
  const file = files[i];
  const rel = relative(webRoot, file);
  const text = allTexts[i];
  const tipIds = collectTipIds(text);
  if (tipIds.length) tipIdsByFile[rel] = tipIds;

  BUTTON_RE.lastIndex = 0;
  let match;
  while ((match = BUTTON_RE.exec(text))) {
    let covered = hasNearbyToolTip(text, match.index);

    if (!covered && ALLOWLIST_FILES.has(rel)) {
      covered = true;
    }

    if (!covered && isPrimitiveInternalButton(text, match.index, rel)) {
      covered = true;
    }

    if (!covered && rel.endsWith("PanelToggle.tsx") && isPanelToggleInsideToolTip(text, match.index)) {
      covered = true;
    }

    buttons.push({
      file: rel,
      line: lineOf(text, match.index),
      snippet: snippetAt(text, match.index),
      covered,
    });
  }
}

const uncovered = buttons.filter((b) => !b.covered);
const manifest = {
  generatedAt: new Date().toISOString(),
  summary: {
    filesScanned: files.length,
    buttonsFound: buttons.length,
    buttonsCovered: buttons.length - uncovered.length,
    buttonsUncovered: uncovered.length,
    coveragePercent:
      buttons.length === 0
        ? 100
        : Math.round(((buttons.length - uncovered.length) / buttons.length) * 1000) / 10,
    wrapperTipIdUsages: wrapperTipIdCounts,
  },
  allowlistedFiles: [...ALLOWLIST_FILES],
  tipIdsByFile,
  uncoveredButtons: uncovered,
};

writeFileSync(outPath, JSON.stringify(manifest, null, 2) + "\n");

console.log(
  `Tooltip audit: ${manifest.summary.buttonsCovered}/${manifest.summary.buttonsFound} buttons covered (${manifest.summary.coveragePercent}%)`,
);
console.log(`Wrote ${relative(webRoot, outPath)}`);
if (uncovered.length) {
  console.log(`Uncovered: ${uncovered.length} (see manifest)`);
}
