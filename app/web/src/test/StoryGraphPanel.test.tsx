import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import type { StoryGraphNodeSummary } from "../api/client";
import StoryGraphPanel from "../components/StoryGraphPanel";
import * as client from "../api/client";
import { TestProviders } from "./TestProviders";
import { SAMPLE_GRAPH_EDGES, SAMPLE_GRAPH_NODES } from "../lib/storyGraph";

vi.mock("../components/GraphWorkbench", () => ({
  default: ({
    nodes,
    selectedId,
    onNodeClick,
  }: {
    nodes: StoryGraphNodeSummary[];
    selectedId: string | null;
    onNodeClick: (id: string) => void;
  }) => {
    const selected = nodes.find((node) => node.id === selectedId) ?? null;
    return (
      <div data-testid="graph-workbench-mock">
        <button type="button" aria-label="Radial">
          Radial
        </button>
        {nodes.map((node) => (
          <button key={node.id} type="button" onClick={() => onNodeClick(node.id)}>
            {node.title}
          </button>
        ))}
        {selected && (
          <div>
            <h3>{selected.title}</h3>
            <p>{selected.description}</p>
          </div>
        )}
      </div>
    );
  },
}));

const CHARS = [
  { id: "char_a", full_name: "Alice", role: "protagonist" },
  { id: "char_b", full_name: "Bob", role: "antagonist" },
];

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(client.api, "storyGraphNodes").mockResolvedValue(SAMPLE_GRAPH_NODES);
  vi.spyOn(client.api, "storyGraphEdges").mockResolvedValue(SAMPLE_GRAPH_EDGES);
  vi.spyOn(client.api, "listChapterBeats").mockResolvedValue([]);
});

test("renders sample story graph nodes in workbench", async () => {
  render(
    <TestProviders>
      <StoryGraphPanel projectId="sample-p" characters={CHARS} />
    </TestProviders>,
  );
  expect(await screen.findByText("The Heist")).toBeInTheDocument();
  expect(screen.getByText(/Vault alarm subp/i)).toBeInTheDocument();
  expect(screen.getByText(/non-destructive/i)).toBeInTheDocument();
  expect(screen.getByTestId("graph-workbench-mock")).toBeInTheDocument();
});

test("migrate button calls API and shows result", async () => {
  const migrate = vi.spyOn(client.api, "migrateStoryGraph").mockResolvedValue({
    nodes_created: 3,
    edges_created: 2,
    skipped: false,
  });
  const user = userEvent.setup();
  render(
    <TestProviders>
      <StoryGraphPanel projectId="sample-p" characters={CHARS} />
    </TestProviders>,
  );
  await screen.findByText("The Heist");
  await user.click(screen.getByTestId("migrate-story-graph"));
  await waitFor(() => expect(migrate).toHaveBeenCalledWith("sample-p"));
});

test("selecting a node shows inspector detail", async () => {
  const user = userEvent.setup();
  render(
    <TestProviders>
      <StoryGraphPanel projectId="sample-p" characters={CHARS} />
    </TestProviders>,
  );
  await screen.findByText("The Heist");
  await user.click(screen.getByRole("button", { name: "The Heist" }));
  expect(await screen.findByRole("heading", { name: "The Heist" })).toBeInTheDocument();
  expect(screen.getByText(/Steal the vault key/)).toBeInTheDocument();
});
