import { ViewportPortal } from "@xyflow/react";
import type { ActBandRect } from "../../lib/storyGraphFlow";

const ACT_TINT: Record<ActBandRect["act"], string> = {
  1: "color-mix(in srgb, var(--color-st-approved) 8%, var(--color-paper-card))",
  2: "color-mix(in srgb, var(--color-st-drafted) 8%, var(--color-paper-card))",
  3: "color-mix(in srgb, var(--color-amber) 10%, var(--color-paper-card))",
};

export default function ActLayerBands({ bands }: { bands: ActBandRect[] }) {
  return (
    <ViewportPortal>
      {bands.map((band) => (
        <div
          key={band.act}
          aria-hidden
          className="pointer-events-none rounded-xl border border-paper-line/70 shadow-[var(--shadow-paper)]"
          style={{
            position: "absolute",
            left: band.x,
            top: band.y,
            width: band.width,
            height: band.height,
            zIndex: -1,
            background: ACT_TINT[band.act],
            transform: `perspective(900px) rotateX(3deg) translateZ(${band.depth}px)`,
            transformOrigin: "50% 100%",
            boxShadow: `0 ${6 + band.depth}px ${14 + band.depth * 2}px rgba(0,0,0,0.06)`,
          }}
        >
          <div
            className="absolute inset-x-0 top-0 h-8 rounded-t-xl border-b border-paper-line/50 px-4 py-1.5"
            style={{
              background:
                "linear-gradient(180deg, color-mix(in srgb, var(--color-paper) 70%, transparent), transparent)",
            }}
          >
            <span className="font-display text-[12px] font-semibold text-ink-text">{band.label}</span>
          </div>
        </div>
      ))}
    </ViewportPortal>
  );
}
