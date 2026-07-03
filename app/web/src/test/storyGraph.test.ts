import { describe, expect, it } from "vitest";
import {
  SAMPLE_GRAPH_EDGES,
  SAMPLE_GRAPH_NODES,
  buildChapterBeatGraph,
  edgeCurvePath,
  focusedStoryGraph,
  isChapterBeatGraphEdgeId,
  isChapterBeatGraphNodeId,
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

  it("turns linked chapter beats into graph leaves", () => {
    const graph = buildChapterBeatGraph(SAMPLE_GRAPH_NODES, SAMPLE_GRAPH_EDGES, {
      3: [
        {
          id: "beat_3_001",
          title: "Crack the alarm",
          summary: "The alarm thread advances.",
          sort_order: 0,
          status: "planned",
          linked_node_ids: ["sg_main"],
        },
      ],
    });

    expect(graph.nodes.some((node) => isChapterBeatGraphNodeId(node.id))).toBe(true);
    expect(graph.edges).toContainEqual(
      expect.objectContaining({
        source_id: "sg_main",
        target_id: "chapter-beat:3:beat_3_001",
        kind: "contains",
      }),
    );
    expect(graph.edges.some((edge) => isChapterBeatGraphEdgeId(edge.id))).toBe(true);
  });

  it("focuses a graph to the selected node and immediate neighbors", () => {
    const focused = focusedStoryGraph(SAMPLE_GRAPH_NODES, SAMPLE_GRAPH_EDGES, "sg_sub2");

    expect(focused.focusId).toBe("sg_sub2");
    expect(focused.nodes.map((node) => node.id).sort()).toEqual(["sg_main", "sg_sub1", "sg_sub2"]);
    expect(focused.incomingIds.has("sg_main")).toBe(true);
    expect(focused.outgoingIds.has("sg_sub1")).toBe(true);
  });
});
