import { describe, expect, it } from "vitest";
import {
  buildContainsHierarchy,
  collectBranchIds,
  filterMatchingNodes,
  lifespanLabel,
  mergeIds,
  nodeEligibleAtChapter,
  nodeMatchesSearch,
  partitionNodesByBriefEligibility,
  removeIds,
} from "../lib/graphFocusPicker";
import { ELIGIBILITY_GRAPH_NODES, SAMPLE_GRAPH_EDGES, SAMPLE_GRAPH_NODES } from "../lib/storyGraph";

const CHAR_NAMES = new Map([
  ["char_a", "Alice"],
  ["char_b", "Bob"],
]);

describe("graphFocusPicker", () => {
  it("matches search across title, kind, status, and linked characters", () => {
    expect(nodeMatchesSearch(SAMPLE_GRAPH_NODES[0], "heist", CHAR_NAMES)).toBe(true);
    expect(nodeMatchesSearch(SAMPLE_GRAPH_NODES[2], "bob", CHAR_NAMES)).toBe(true);
    expect(nodeMatchesSearch(SAMPLE_GRAPH_NODES[2], "foreshadowed", CHAR_NAMES)).toBe(true);
    expect(nodeMatchesSearch(SAMPLE_GRAPH_NODES[1], "alice", CHAR_NAMES)).toBe(false);
  });

  it("filters nodes by kind and status", () => {
    const subplotOnly = filterMatchingNodes(
      SAMPLE_GRAPH_NODES,
      { search: "", kind: "subplot", status: "all" },
      CHAR_NAMES,
    );
    expect(subplotOnly.map((n) => n.id)).toEqual(["sg_sub1", "sg_sub2"]);

    const foreshadowed = filterMatchingNodes(
      SAMPLE_GRAPH_NODES,
      { search: "", kind: "all", status: "foreshadowed" },
      CHAR_NAMES,
    );
    expect(foreshadowed.map((n) => n.id)).toEqual(["sg_sub2"]);
  });

  it("builds contains hierarchy and branch ids", () => {
    const hierarchy = buildContainsHierarchy(SAMPLE_GRAPH_NODES, SAMPLE_GRAPH_EDGES);
    expect(hierarchy.roots).toEqual(["sg_main"]);
    expect(hierarchy.children.get("sg_main")).toEqual(["sg_sub2", "sg_sub1"]);
    expect(hierarchy.orphans).toEqual([]);
    expect(collectBranchIds("sg_main", hierarchy.children)).toEqual([
      "sg_main",
      "sg_sub2",
      "sg_sub1",
    ]);
  });

  it("merges and removes ids without duplicates", () => {
    expect(mergeIds(["a"], ["b", "a"])).toEqual(["a", "b"]);
    expect(removeIds(["a", "b", "c"], ["b"])).toEqual(["a", "c"]);
  });

  it("nodeEligibleAtChapter respects start and resolution", () => {
    const eligible = SAMPLE_GRAPH_NODES.find((node) => node.id === "sg_sub1")!;
    const past = ELIGIBILITY_GRAPH_NODES.find((node) => node.id === "sg_past")!;
    const future = ELIGIBILITY_GRAPH_NODES.find((node) => node.id === "sg_future")!;

    expect(nodeEligibleAtChapter(eligible, 3)).toBe(true);
    expect(nodeEligibleAtChapter(past, 3)).toBe(false);
    expect(nodeEligibleAtChapter(future, 3)).toBe(false);
    expect(nodeEligibleAtChapter({ ...eligible, start_chapter: 0 }, 1)).toBe(true);
  });

  it("partitionNodesByBriefEligibility splits in-effect, eligible, and out-of-range", () => {
    const partition = partitionNodesByBriefEligibility(
      ELIGIBILITY_GRAPH_NODES,
      3,
      ["sg_main", "sg_sub2"],
    );
    expect(partition.inEffect.map((node) => node.id)).toEqual(["sg_main", "sg_sub2"]);
    expect(partition.eligibleNotInEffect.map((node) => node.id)).toEqual(["sg_sub1"]);
    expect(partition.outOfRange.map((node) => node.id)).toEqual(["sg_past", "sg_future"]);
  });

  it("lifespanLabel formats open and closed ranges", () => {
    expect(lifespanLabel(SAMPLE_GRAPH_NODES[0])).toBe("Ch. 1–");
    expect(lifespanLabel(SAMPLE_GRAPH_NODES[1])).toBe("Ch. 2–8");
    expect(lifespanLabel(ELIGIBILITY_GRAPH_NODES.find((node) => node.id === "sg_past")!)).toBe("Ch. 1");
  });
});
