import { describe, expect, it } from "vitest";
import {
  SAMPLE_GRAPH_EDGES,
  SAMPLE_GRAPH_NODES,
  edgeCurvePath,
  kindLabel,
  mindMapLayout,
  nodeDisplayEdges,
} from "../lib/storyGraph";

describe("storyGraph utils", () => {
  it("filters display edges to graph node endpoints", () => {
    const edges = [
      ...SAMPLE_GRAPH_EDGES,
      { id: "cr", source_id: "char_a", target_id: "char_b", kind: "character_relationship", label: "rival" },
    ];
    const display = nodeDisplayEdges(SAMPLE_GRAPH_NODES, edges);
    expect(display).toHaveLength(3);
    expect(display.every((e) => e.kind !== "character_relationship")).toBe(true);
  });

  it("layouts sample nodes in layers via contains edges", () => {
    const { layout, height } = mindMapLayout(SAMPLE_GRAPH_NODES, SAMPLE_GRAPH_EDGES);
    expect(layout).toHaveLength(3);
    expect(height).toBeGreaterThan(150);
    const main = layout.find((n) => n.id === "sg_main");
    const sub1 = layout.find((n) => n.id === "sg_sub1");
    expect(main).toBeDefined();
    expect(sub1).toBeDefined();
    expect(main!.y).toBeLessThan(sub1!.y);
  });

  it("produces a curved SVG path between points", () => {
    const path = edgeCurvePath({ x: 10, y: 10 }, { x: 100, y: 50 });
    expect(path).toMatch(/^M 10 10 Q/);
    expect(path).toContain("100 50");
  });

  it("formats kind labels", () => {
    expect(kindLabel("plot_thread")).toBe("plot thread");
    expect(kindLabel("character_arc")).toBe("character arc");
  });
});
