import { describe, expect, it } from "vitest";
import {
  computeRelationshipLayout,
  reciprocalEdgeStyle,
  toRelationshipFlowEdges,
  toRelationshipFlowNodes,
} from "../lib/relationshipGraphFlow";
import { buildRelationshipEdges } from "../lib/characterRelationships";

describe("relationshipGraphFlow", () => {
  const characters = [
    { id: "a", full_name: "Alice", role: "protagonist", relationships: { b: "mother" } },
    { id: "b", full_name: "Beth", role: "supporting", relationships: {} },
    { id: "c", full_name: "Carl", role: "minor", relationships: {} },
  ];

  it("computes radial positions for all cast members", () => {
    const positions = computeRelationshipLayout(["a", "b", "c"], {});
    expect(positions.size).toBe(3);
    for (const id of ["a", "b", "c"]) {
      expect(positions.get(id)).toBeDefined();
    }
  });

  it("prefers saved layout over auto layout", () => {
    const saved = { a: { x: 10, y: 20 } };
    const positions = computeRelationshipLayout(["a", "b"], saved);
    expect(positions.get("a")).toEqual({ x: 10, y: 20 });
    expect(positions.get("b")).toBeDefined();
  });

  it("builds flow nodes and edges from relationship data", () => {
    const edges = buildRelationshipEdges(characters);
    const nameById = new Map(characters.map((c) => [c.id, c.full_name]));
    const roleById = new Map(characters.map((c) => [c.id, c.role]));
    const positions = computeRelationshipLayout(characters.map((c) => c.id), {});

    const nodes = toRelationshipFlowNodes(
      characters.map((c) => c.id),
      nameById,
      roleById,
      positions,
      { selectedId: "a" },
    );
    expect(nodes).toHaveLength(3);
    expect(nodes.find((n) => n.id === "a")?.data.selected).toBe(true);

    const flowEdges = toRelationshipFlowEdges(edges);
    expect(flowEdges).toHaveLength(1);
    expect(flowEdges[0].label).toBe("mother");
    expect(flowEdges[0].data?.labelSide).toBe(0);
  });

  it("offsets reciprocal edge curves and labels", () => {
    const reciprocal = [
      { id: "mom", full_name: "Mother", role: "minor", relationships: { jack: "son" } },
      { id: "jack", full_name: "Jack", role: "protagonist", relationships: { mom: "mother" } },
    ];
    const edges = buildRelationshipEdges(reciprocal);
    const keys = new Set(edges.map((e) => `${e.fromId}|${e.toId}`));
    const momToJack = edges.find((e) => e.fromId === "mom")!;
    const jackToMom = edges.find((e) => e.fromId === "jack")!;
    const momStyle = reciprocalEdgeStyle(momToJack, keys);
    const jackStyle = reciprocalEdgeStyle(jackToMom, keys);
    expect(momStyle.labelSide).not.toBe(0);
    expect(jackStyle.labelSide).not.toBe(0);
    expect(momStyle.labelSide).toBe(-jackStyle.labelSide);
    expect(momStyle.sourceHandle).not.toBe(jackStyle.sourceHandle);
    expect(momStyle.targetHandle).not.toBe(jackStyle.targetHandle);
    expect(momStyle.labelPosition).not.toBe(jackStyle.labelPosition);
    expect(momStyle.labelPosition).toBeGreaterThan(0.5);
    expect(jackStyle.labelPosition).toBeLessThan(0.5);

    const flowEdges = toRelationshipFlowEdges(edges);
    expect(flowEdges).toHaveLength(2);
    const handles = flowEdges.map((e) => `${e.sourceHandle}->${e.targetHandle}`);
    expect(handles).toContain("source-bottom->target-top");
    expect(handles).toContain("source-right->target-left");
  });
});
