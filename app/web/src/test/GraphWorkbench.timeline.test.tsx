import { type ComponentProps } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import type { Node, NodeChange } from "@xyflow/react";
import GraphWorkbench from "../components/GraphWorkbench";
import * as client from "../api/client";
import { TestProviders } from "./TestProviders";
import { SAMPLE_GRAPH_EDGES, SAMPLE_GRAPH_NODES } from "../lib/storyGraph";
import {
  GRAPH_VIEW_MODE_KEY,
  type StoryGraphFlowNodeData,
} from "../lib/storyGraphFlow";

const CHAPTERS: client.ChapterSummary[] = [
  { number: 1, title: "Setup", status: "planned", word_count: 0, pov: "", pipeline_step: "none" },
  { number: 2, title: "Vault", status: "planned", word_count: 800, pov: "Alice", pipeline_step: "drafted" },
];

const CHARS = [
  { id: "char_a", full_name: "Alice", role: "protagonist" },
];

let capturedOnNodesChange:
  | ((changes: NodeChange<Node<StoryGraphFlowNodeData>>[]) => void)
  | null = null;

vi.mock("@xyflow/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@xyflow/react")>();
  return {
    ...actual,
    ReactFlow: ({
      nodes,
      onNodesChange,
      children,
    }: {
      nodes: Node<StoryGraphFlowNodeData>[];
      onNodesChange?: (changes: NodeChange<Node<StoryGraphFlowNodeData>>[]) => void;
      children?: React.ReactNode;
    }) => {
      capturedOnNodesChange = onNodesChange ?? null;
      return (
        <div data-testid="react-flow-mock">
          {nodes.map((node) => (
            <button key={node.id} type="button" data-testid={`flow-node-${node.id}`}>
              {node.data.node.title}
            </button>
          ))}
          {children}
        </div>
      );
    },
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    useReactFlow: () => ({
      fitView: vi.fn(),
      setCenter: vi.fn(),
    }),
    ViewportPortal: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    applyNodeChanges: actual.applyNodeChanges,
    Background: () => null,
    Controls: () => null,
  };
});

function renderWorkbench(
  overrides?: Partial<ComponentProps<typeof GraphWorkbench>>,
) {
  return render(
    <TestProviders>
      <GraphWorkbench
        projectId="sample-p"
        nodes={SAMPLE_GRAPH_NODES.map((node) =>
          node.id === "sg_main"
            ? { ...node, act: 1, chapter_pins: [1] }
            : { ...node, act: 2, chapter_pins: [] },
        )}
        edges={SAMPLE_GRAPH_EDGES}
        characters={CHARS}
        chapters={CHAPTERS}
        selectedId={null}
        linkSourceId={null}
        onSelectNode={vi.fn()}
        onNodeClick={vi.fn()}
        onEditNode={vi.fn()}
        onDeleteNode={vi.fn()}
        onDeleteEdge={vi.fn()}
        onNodesChange={vi.fn()}
        {...overrides}
      />
    </TestProviders>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  capturedOnNodesChange = null;
  localStorage.removeItem(GRAPH_VIEW_MODE_KEY);
});

test("enables Acts and Timeline tabs and persists view mode", async () => {
  const user = userEvent.setup();
  renderWorkbench();

  const acts = screen.getByRole("button", { name: "Acts" });
  const timeline = screen.getByRole("button", { name: "Timeline" });
  expect(acts).toBeEnabled();
  expect(timeline).toBeEnabled();

  await user.click(acts);
  expect(localStorage.getItem(GRAPH_VIEW_MODE_KEY)).toBe("acts");
  await user.click(timeline);
  expect(localStorage.getItem(GRAPH_VIEW_MODE_KEY)).toBe("timeline");
});

test("timeline breadcrumb navigates act overview and chapter drill-down", async () => {
  const user = userEvent.setup();
  renderWorkbench();

  await user.click(screen.getByRole("button", { name: "Timeline" }));
  expect(screen.getByRole("navigation", { name: "Timeline view" })).toBeInTheDocument();
  expect(screen.getByText("Act overview")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Chapter drill-down" }));
  expect(screen.getByText("Chapter pins")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Back to acts" }));
  expect(screen.queryByText("Chapter pins")).not.toBeInTheDocument();
});

test("act drag stop PATCHes act assignment", async () => {
  const user = userEvent.setup();
  const update = vi.spyOn(client.api, "updateStoryGraphNode").mockResolvedValue({
    ...SAMPLE_GRAPH_NODES[0],
    act: 2,
  });
  renderWorkbench();

  await user.click(screen.getByRole("button", { name: "Acts" }));
  expect(capturedOnNodesChange).toBeTruthy();
  capturedOnNodesChange!([
    {
      id: "sg_main",
      type: "position",
      dragging: false,
      position: { x: 400, y: 320 },
    },
  ]);

  await waitFor(() =>
    expect(update).toHaveBeenCalledWith("sample-p", "sg_main", { act: 2 }),
  );
});

test("timeline chapter drag stop pins node via pin endpoint", async () => {
  const user = userEvent.setup();
  const pin = vi.spyOn(client.api, "pinStoryGraphNode").mockResolvedValue({
    ...SAMPLE_GRAPH_NODES[0],
    chapter_pins: [2],
  });

  renderWorkbench();
  await user.click(screen.getByRole("button", { name: "Timeline" }));
  await user.click(screen.getByRole("button", { name: "Chapter drill-down" }));

  capturedOnNodesChange!([
    {
      id: "sg_main",
      type: "position",
      dragging: false,
      position: { x: 420, y: 120 },
    },
  ]);

  await waitFor(() =>
    expect(pin).toHaveBeenCalledWith("sample-p", "sg_main", {
      chapter_number: 1,
      pinned: false,
    }),
  );
  await waitFor(() =>
    expect(pin).toHaveBeenCalledWith("sample-p", "sg_main", {
      chapter_number: 2,
      pinned: true,
    }),
  );
});

test("inspector shows act and chapter pins for selected node", async () => {
  renderWorkbench({ selectedId: "sg_main" });
  expect(screen.getByText("Act")).toBeInTheDocument();
  expect(screen.getByText("Act 1")).toBeInTheDocument();
  expect(screen.getByText("Chapter pins")).toBeInTheDocument();
  expect(screen.getAllByText(/Ch\. 1/).length).toBeGreaterThanOrEqual(2);
});
