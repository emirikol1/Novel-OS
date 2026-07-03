import { describe, expect, it } from "vitest";
import {
  BINDER_WIDTH,
  CENTER_STUDIO_GUTTER_PX,
  clampPanelWidth,
  computeFluidManuscriptLayout,
  computeInspectorMaxWidth,
  INSPECTOR_WIDTH_DEFAULT,
  INSPECTOR_WIDTH_MAX,
  INSPECTOR_WIDTH_MIN,
} from "../lib/chapterStudioLayout";

describe("chapterStudioLayout", () => {
  it("clamps panel widths", () => {
    expect(clampPanelWidth(100, INSPECTOR_WIDTH_MIN, INSPECTOR_WIDTH_MAX, INSPECTOR_WIDTH_DEFAULT)).toBe(
      INSPECTOR_WIDTH_MIN,
    );
    expect(clampPanelWidth(999, INSPECTOR_WIDTH_MIN, INSPECTOR_WIDTH_MAX, INSPECTOR_WIDTH_DEFAULT)).toBe(
      INSPECTOR_WIDTH_MAX,
    );
    expect(clampPanelWidth(320, INSPECTOR_WIDTH_MIN, INSPECTOR_WIDTH_MAX, INSPECTOR_WIDTH_DEFAULT)).toBe(320);
  });

  it("uses a fixed minimum binder width", () => {
    expect(BINDER_WIDTH).toBe(152);
  });

  it("keeps manuscript column width at the page measure", () => {
    const narrowCenter = computeFluidManuscriptLayout(520, "normal");
    const wideCenter = computeFluidManuscriptLayout(1100, "wide");

    expect(narrowCenter.columnMaxPx).toBe(672);
    expect(wideCenter.columnMaxPx).toBe(832);
    expect(wideCenter.fontRem).toBeGreaterThan(narrowCenter.fontRem);
  });

  it("limits inspector width so the page column is not squeezed", () => {
    const max = computeInspectorMaxWidth(1200, "normal", true);
    const reserved = BINDER_WIDTH + 672 + CENTER_STUDIO_GUTTER_PX + 8;
    expect(max).toBe(1200 - reserved);
  });
});
