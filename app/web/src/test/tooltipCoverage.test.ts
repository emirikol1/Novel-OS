import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "../..");
const manifestPath = join(webRoot, "src/lib/tooltipManifest.json");

type TooltipManifest = {
  summary: {
    coveragePercent: number;
    buttonsUncovered: number;
  };
  allowlistedFiles: string[];
  uncoveredButtons: Array<{ file: string; line: number }>;
};

/**
 * Buttons in meta tooltip UI (ToolTipDock, ToolTipDetail) are allowlisted in
 * scripts/audit-tooltips.mjs — not product controls requiring registry entries.
 */
const AUDIT_ALLOWLISTED_FILES = new Set([
  "src/components/ToolTipDock.tsx",
  "src/components/ToolTipDetail.tsx",
]);

const MIN_COVERAGE_PERCENT = 95;

function loadManifest(): TooltipManifest {
  return JSON.parse(readFileSync(manifestPath, "utf8")) as TooltipManifest;
}

describe("tooltip coverage manifest", () => {
  it("meets minimum coverage threshold", () => {
    const manifest = loadManifest();
    expect(manifest.summary.coveragePercent).toBeGreaterThanOrEqual(MIN_COVERAGE_PERCENT);
  });

  it("has no uncovered buttons beyond audit allowlist", () => {
    const manifest = loadManifest();
    const realGaps = manifest.uncoveredButtons.filter(
      (b) => !AUDIT_ALLOWLISTED_FILES.has(b.file),
    );
    expect(realGaps).toEqual([]);
    expect(manifest.summary.buttonsUncovered).toBeLessThanOrEqual(AUDIT_ALLOWLISTED_FILES.size);
  });

  it("documents allowlisted meta-tooltip files in manifest", () => {
    const manifest = loadManifest();
    for (const file of AUDIT_ALLOWLISTED_FILES) {
      expect(manifest.allowlistedFiles).toContain(file);
    }
  });
});
