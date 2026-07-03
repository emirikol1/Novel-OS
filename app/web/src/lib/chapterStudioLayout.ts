import type { Measure } from "../components/ManuscriptControls";

/** Fixed binder column — fits chapter number, dot, and truncated title with margins. */
export const BINDER_WIDTH = 152;

export const INSPECTOR_WIDTH_DEFAULT = 320;
export const INSPECTOR_WIDTH_MIN = 240;
export const INSPECTOR_WIDTH_MAX = 520;

/** Reference content width (~42rem) for default manuscript size. */
export const MANUSCRIPT_REF_WIDTH_PX = 672;

const MEASURE_CAP_PX: Record<Measure, number> = {
  narrow: 544,
  normal: 672,
  wide: 832,
};

/** Horizontal padding reserved around the manuscript column in the studio center pane. */
export const CENTER_STUDIO_GUTTER_PX = 64;

export const PANEL_RESIZE_HANDLE_PX = 8;

export function manuscriptColumnPx(measure: Measure = "normal"): number {
  return MEASURE_CAP_PX[measure];
}

export function computeInspectorMaxWidth(
  studioWidth: number,
  measure: Measure,
  binderVisible: boolean,
): number {
  if (studioWidth <= 0) return INSPECTOR_WIDTH_MAX;
  const columnPx = manuscriptColumnPx(measure);
  const reserved =
    (binderVisible ? BINDER_WIDTH : 0) +
    columnPx +
    CENTER_STUDIO_GUTTER_PX +
    PANEL_RESIZE_HANDLE_PX;
  return clampPanelWidth(
    studioWidth - reserved,
    INSPECTOR_WIDTH_MIN,
    INSPECTOR_WIDTH_MAX,
    INSPECTOR_WIDTH_DEFAULT,
  );
}

export function clampPanelWidth(
  value: number,
  min: number,
  max: number,
  fallback: number,
): number {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(max, Math.max(min, Math.round(value)));
}

export function computeFluidManuscriptLayout(
  contentWidthPx: number,
  measure: Measure = "normal",
) {
  const columnMaxPx = MEASURE_CAP_PX[measure];
  const scaleSource = Math.max(Math.max(0, contentWidthPx), columnMaxPx);
  const scale = clamp(scaleSource / MANUSCRIPT_REF_WIDTH_PX, 0.82, 1.34);
  const fontRem = clamp(1.075 * scale, 0.92, 1.44);
  return { scale, fontRem, columnMaxPx };
}

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n));
}
