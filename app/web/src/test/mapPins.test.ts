import { describe, expect, it } from "vitest";
import {
  clampCoord,
  formatLoreReference,
  pointerToNormalized,
} from "../lib/mapPins";

describe("mapPins", () => {
  it("clamps coordinates to 0..1", () => {
    expect(clampCoord(0.5)).toBe(0.5);
    expect(clampCoord(-1)).toBe(0);
    expect(clampCoord(2)).toBe(1);
    expect(clampCoord(Number.NaN)).toBe(0);
  });

  it("converts pointer position to normalized coords", () => {
    const rect = { left: 100, top: 50, width: 200, height: 100 } as DOMRect;
    expect(pointerToNormalized(150, 100, rect)).toEqual({ x: 0.25, y: 0.5 });
    expect(pointerToNormalized(50, 0, rect)).toEqual({ x: 0, y: 0 });
  });

  it("formats lore references", () => {
    expect(formatLoreReference("setting_summary", "Old Harbor")).toBe(
      "setting_summary: Old Harbor",
    );
    expect(formatLoreReference("", "Harbor")).toBe("Harbor");
    expect(formatLoreReference("tone", "")).toBe("tone");
  });
});
