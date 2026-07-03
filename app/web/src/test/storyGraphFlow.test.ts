import { describe, expect, it } from "vitest";
import type { ChapterSummary } from "../api/client";
import {
  SAMPLE_GRAPH_EDGES,
  SAMPLE_GRAPH_NODES,
} from "../lib/storyGraph";
import {
  actAtPosition,
  computeActBandRects,
  computeActLayerLayout,
  computeRadialLayout,
  computeTimelineActColumns,
  computeTimelineActOverviewLayout,
  computeTimelineChapterColumns,
  computeTimelineChapterLayout,
  fromFlowPosition,
  mergePersistedLayout,
  primaryPinChapter,
  resolveNodeAct,
  timelineActAtPosition,
  timelineChapterAtPosition,
  toFlowEdges,
  toFlowNodes,
} from "../lib/storyGraphFlow";

const CHAPTERS: ChapterSummary[] = [
  { number: 1, title: "Setup", status: "planned", word_count: 0, pov: "", pipeline_step: "none" },
  { number: 2, title: "Complication", status: "planned", word_count: 500, pov: "Alice", pipeline_step: "drafted" },
  { number: 3, title: "Vault", status: "planned", word_count: 1200, pov: "Alice", pipeline_step: "drafted" },
];

describe("storyGraphFlow", () => {
  it("computes radial positions for all sample nodes", () => {
    const positions = computeRadialLayout(SAMPLE_GRAPH_NODES, SAMPLE_GRAPH_EDGES);
    expect(positions.size).toBe(3);
    expect(positions.get("sg_main")).toBeDefined();
    expect(positions.get("sg_sub1")).toBeDefined();
    expect(positions.get("sg_sub2")).toBeDefined();
  });

  it("places main node near center in contains tree", () => {
    const positions = computeRadialLayout(SAMPLE_GRAPH_NODES, SAMPLE_GRAPH_EDGES, {
      x: 400,
      y: 320,
    });
    const main = positions.get("sg_main")!;
    const sub1 = positions.get("sg_sub1")!;
    const mainDist = Math.hypot(main.x - 400, main.y - 320);
    const subDist = Math.hypot(sub1.x - 400, sub1.y - 320);
    expect(mainDist).toBeLessThan(subDist);
  });

  it("prefers persisted layout over computed positions", () => {
    const computed = computeRadialLayout(SAMPLE_GRAPH_NODES, SAMPLE_GRAPH_EDGES);
    const nodes = SAMPLE_GRAPH_NODES.map((node) =>
      node.id === "sg_main"
        ? { ...node, layout: { x: 42, y: 99 } }
        : node,
    );
    const merged = mergePersistedLayout(nodes, computed);
    expect(merged.get("sg_main")).toEqual({ x: 42, y: 99 });
    expect(merged.get("sg_sub1")).toEqual(computed.get("sg_sub1"));
  });

  it("maps nodes and edges to React Flow shapes", () => {
    const charNames = new Map([["char_a", "Alice"]]);
    const flowNodes = toFlowNodes(SAMPLE_GRAPH_NODES, SAMPLE_GRAPH_EDGES, { charNames });
    const flowEdges = toFlowEdges(SAMPLE_GRAPH_NODES, SAMPLE_GRAPH_EDGES);

    expect(flowNodes).toHaveLength(3);
    expect(flowNodes[0].type).toBe("storyGraphNode");
    expect(flowNodes[0].data.node.title).toBe("The Heist");

    expect(flowEdges).toHaveLength(3);
    expect(flowEdges[0].type).toBe("storyGraphEdge");
    expect(flowEdges.every((e) => e.source && e.target)).toBe(true);
  });

  it("rounds flow positions for API persistence", () => {
    expect(fromFlowPosition({ x: 12.3456, y: -7.891 })).toEqual({ x: 12.3, y: -7.9 });
  });

  it("resolveNodeAct prefers explicit act over start_chapter", () => {
    const node = { ...SAMPLE_GRAPH_NODES[0], act: 3, start_chapter: 1 };
    expect(resolveNodeAct(node, 9)).toBe(3);
  });

  it("resolveNodeAct infers act from start_chapter when act unset", () => {
    expect(resolveNodeAct(SAMPLE_GRAPH_NODES[0], 9)).toBe(1);
    expect(resolveNodeAct(SAMPLE_GRAPH_NODES[1], 9)).toBe(1);
  });

  it("computeActLayerLayout places nodes inside their act bands", () => {
    const nodes = [
      { ...SAMPLE_GRAPH_NODES[0], act: 1 },
      { ...SAMPLE_GRAPH_NODES[1], act: 2 },
      { ...SAMPLE_GRAPH_NODES[2], act: 3 },
    ];
    const { positions, bands } = computeActLayerLayout(nodes, { chapterCount: 9 });
    expect(bands).toHaveLength(3);

    const act1Band = bands[0];
    const act2Band = bands[1];
    const act3Band = bands[2];
    const n1 = positions.get("sg_main")!;
    const n2 = positions.get("sg_sub1")!;
    const n3 = positions.get("sg_sub2")!;

    expect(n1.y).toBeGreaterThanOrEqual(act1Band.y);
    expect(n1.y).toBeLessThan(act1Band.y + act1Band.height);
    expect(n2.y).toBeGreaterThanOrEqual(act2Band.y);
    expect(n2.y).toBeLessThan(act2Band.y + act2Band.height);
    expect(n3.y).toBeGreaterThanOrEqual(act3Band.y);
    expect(n3.y).toBeLessThan(act3Band.y + act3Band.height);
  });

  it("actAtPosition maps y coordinate to act band", () => {
    const bands = computeActBandRects();
    expect(actAtPosition(bands[0].y + 10, bands)).toBe(1);
    expect(actAtPosition(bands[1].y + 10, bands)).toBe(2);
    expect(actAtPosition(bands[2].y + 10, bands)).toBe(3);
  });

  it("computeTimelineActOverviewLayout stacks nodes in act columns", () => {
    const nodes = [
      { ...SAMPLE_GRAPH_NODES[0], act: 1 },
      { ...SAMPLE_GRAPH_NODES[1], act: 2 },
    ];
    const positions = computeTimelineActOverviewLayout(nodes, { chapterCount: 9 });
    const columns = computeTimelineActColumns();
    const col1 = columns[0];
    const col2 = columns[1];
    expect(positions.get("sg_main")!.x).toBeGreaterThanOrEqual(col1.x);
    expect(positions.get("sg_main")!.x).toBeLessThan(col1.x + col1.width);
    expect(positions.get("sg_sub1")!.x).toBeGreaterThanOrEqual(col2.x);
    expect(positions.get("sg_sub1")!.x).toBeLessThan(col2.x + col2.width);
  });

  it("timelineActAtPosition maps x coordinate to act column", () => {
    const columns = computeTimelineActColumns();
    expect(timelineActAtPosition(columns[0].x + 10, columns)).toBe(1);
    expect(timelineActAtPosition(columns[2].x + 10, columns)).toBe(3);
  });

  it("computeTimelineChapterLayout places pinned nodes in chapter columns", () => {
    const nodes = [
      { ...SAMPLE_GRAPH_NODES[0], chapter_pins: [2] },
      { ...SAMPLE_GRAPH_NODES[1], chapter_pins: [3] },
      { ...SAMPLE_GRAPH_NODES[2], chapter_pins: [] },
    ];
    const positions = computeTimelineChapterLayout(nodes, CHAPTERS);
    const columns = computeTimelineChapterColumns(CHAPTERS);
    const pool = columns[0];
    const ch2 = columns.find((c) => c.chapterNumber === 2)!;
    const ch3 = columns.find((c) => c.chapterNumber === 3)!;

    expect(primaryPinChapter(nodes[0])).toBe(2);
    expect(positions.get("sg_main")!.x).toBeGreaterThanOrEqual(ch2.x);
    expect(positions.get("sg_sub1")!.x).toBeGreaterThanOrEqual(ch3.x);
    expect(positions.get("sg_sub2")!.x).toBeGreaterThanOrEqual(pool.x);
    expect(positions.get("sg_sub2")!.x).toBeLessThan(pool.x + pool.width);
  });

  it("timelineChapterAtPosition maps x to chapter or pool column", () => {
    const columns = computeTimelineChapterColumns(CHAPTERS);
    expect(timelineChapterAtPosition(columns[0].x + 10, columns)).toBe(0);
    expect(timelineChapterAtPosition(columns[1].x + 10, columns)).toBe(1);
    expect(timelineChapterAtPosition(columns[3].x + 10, columns)).toBe(3);
  });

  it("toFlowNodes uses act layout mode without persisted radial layout", () => {
    const nodes = SAMPLE_GRAPH_NODES.map((node) =>
      node.id === "sg_main" ? { ...node, layout: { x: 1, y: 1 }, act: 2 } : node,
    );
    const flowNodes = toFlowNodes(nodes, SAMPLE_GRAPH_EDGES, {
      charNames: new Map(),
      layoutMode: "acts",
      chapterCount: 9,
    });
    const main = flowNodes.find((n) => n.id === "sg_main")!;
    expect(main.position).not.toEqual({ x: 1, y: 1 });
    const { bands } = computeActLayerLayout(nodes, { chapterCount: 9 });
    expect(main.position.y).toBeGreaterThanOrEqual(bands[1].y);
  });
});
