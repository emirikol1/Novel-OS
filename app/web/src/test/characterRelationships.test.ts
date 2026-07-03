import { describe, expect, it } from "vitest";
import {
  buildFamilyLinks,
  buildGenealogyForest,
  buildRelationshipEdges,
  classifyRelationshipLabel,
  normalizeRelationshipLabel,
} from "../lib/characterRelationships";

describe("characterRelationships", () => {
  it("normalizes relationship labels", () => {
    expect(normalizeRelationshipLabel("  Mother (biological) ")).toBe("mother biological");
  });

  it("classifies family relationship labels", () => {
    expect(classifyRelationshipLabel("mother")).toBe("parent");
    expect(classifyRelationshipLabel("estranged father")).toBe("parent");
    expect(classifyRelationshipLabel("younger sister")).toBe("sibling");
    expect(classifyRelationshipLabel("husband")).toBe("spouse");
    expect(classifyRelationshipLabel("adoptive mother")).toBe("adopted");
    expect(classifyRelationshipLabel("mentor")).toBeNull();
  });

  it("builds directed edges from character relationship maps", () => {
    const edges = buildRelationshipEdges([
      { id: "a", full_name: "Alice", relationships: { b: "mother", c: "rival" } },
      { id: "b", full_name: "Beth", relationships: {} },
      { id: "c", full_name: "Carl", relationships: {} },
    ]);
    expect(edges).toHaveLength(2);
    expect(edges[0]).toMatchObject({ fromId: "a", toId: "b", label: "mother", familyKind: "parent" });
    expect(edges[1]).toMatchObject({ fromId: "a", toId: "c", label: "rival", familyKind: null });
  });

  it("ignores edges to unknown character ids", () => {
    const edges = buildRelationshipEdges([
      { id: "a", full_name: "Alice", relationships: { ghost: "friend" } },
    ]);
    expect(edges).toHaveLength(0);
  });

  it("derives parent-child links for genealogy", () => {
    const edges = buildRelationshipEdges([
      { id: "child", full_name: "Kid", relationships: { parent: "mother" } },
      { id: "parent", full_name: "Mom", relationships: { child: "son" } },
    ]);
    const links = buildFamilyLinks(edges);
    expect(links.some((l) => l.directed && l.fromId === "parent" && l.toId === "child")).toBe(true);
  });

  it("builds genealogy forest from parent links", () => {
    const cast = [
      { id: "g", full_name: "Grandma", role: "supporting", relationships: {} },
      { id: "p", full_name: "Parent", role: "protagonist", relationships: { g: "mother" } },
      { id: "c", full_name: "Child", role: "minor", relationships: { p: "father" } },
    ];
    const links = buildFamilyLinks(buildRelationshipEdges(cast));
    const forest = buildGenealogyForest(cast, links);
    expect(forest).toHaveLength(1);
    expect(forest[0].name).toBe("Grandma");
    expect(forest[0].children[0]?.name).toBe("Parent");
    expect(forest[0].children[0]?.children[0]?.name).toBe("Child");
  });
});
