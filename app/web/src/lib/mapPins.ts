/** Normalized map pin coordinates and lore reference helpers. */

export function clampCoord(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

export function pointerToNormalized(
  clientX: number,
  clientY: number,
  rect: DOMRect,
): { x: number; y: number } {
  if (rect.width <= 0 || rect.height <= 0) {
    return { x: 0.5, y: 0.5 };
  }
  return {
    x: clampCoord((clientX - rect.left) / rect.width),
    y: clampCoord((clientY - rect.top) / rect.height),
  };
}

export function formatLoreReference(section: string, label: string): string {
  const sec = section.trim();
  const lbl = label.trim();
  if (sec && lbl) return `${sec}: ${lbl}`;
  return lbl || sec;
}

export function loreReferenceFromFields(section: string, label: string): string {
  return formatLoreReference(section, label);
}
