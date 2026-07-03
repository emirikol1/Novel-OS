import { useState } from "react";
import type {
  CharacterSummary,
  StoryGraphEdgeSummary,
  StoryGraphNodeSummary,
} from "../api/client";
import { removeIds } from "../lib/graphFocusPicker";
import CreatePlotFromBriefModal from "./CreatePlotFromBriefModal";
import GraphFocusPicker from "./GraphFocusPicker";
import Modal from "./Modal";
import SelectedGraphNodeChips from "./SelectedGraphNodeChips";
import ToolTip from "./ToolTip";

type ChapterGraphFocusSectionProps = {
  projectId: string;
  chapterNumber: number;
  nodes: StoryGraphNodeSummary[];
  edges?: StoryGraphEdgeSummary[];
  characters: CharacterSummary[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  onGraphNodesChange?: (nodes: StoryGraphNodeSummary[]) => void;
};

export default function ChapterGraphFocusSection({
  projectId,
  chapterNumber,
  nodes,
  edges,
  characters,
  selectedIds,
  onChange,
  onGraphNodesChange,
}: ChapterGraphFocusSectionProps) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const inEffectCount = selectedIds.length;

  function handleNodeCreated(node: StoryGraphNodeSummary) {
    const nextNodes = nodes.some((existing) => existing.id === node.id)
      ? nodes.map((existing) => (existing.id === node.id ? node : existing))
      : [...nodes, node];
    onGraphNodesChange?.(nextNodes);
    if (!selectedIds.includes(node.id)) {
      onChange([...selectedIds, node.id]);
    }
  }

  return (
    <section className="space-y-2" data-testid="chapter-graph-focus-section">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Plots & subplots in effect
        </p>
        <span className="text-[11px] text-ink-muted">{inEffectCount} in effect</span>
      </div>

      {inEffectCount === 0 ? (
        <p className="text-[12px] text-ink-muted">
          No plots in effect — eligible plots can be added below.
        </p>
      ) : (
        <SelectedGraphNodeChips
          nodes={nodes}
          selectedIds={selectedIds}
          onRemove={(id) => onChange(removeIds(selectedIds, [id]))}
        />
      )}

      <div className="flex flex-wrap gap-3">
        <ToolTip id="chapter.graphAddPlot">
          <button
            type="button"
            onClick={() => setPickerOpen(true)}
            disabled={nodes.length === 0}
            className="text-[12px] font-medium text-ink-text hover:underline disabled:cursor-not-allowed disabled:opacity-40"
          >
            + Add plot/subplot
          </button>
        </ToolTip>
        <ToolTip id="chapter.graphNewPlot">
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="text-[12px] font-medium text-ink-text hover:underline"
          >
            + New plot/subplot
          </button>
        </ToolTip>
      </div>

      <Modal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        title="Add plot/subplot to chapter"
        size="wide"
      >
        <GraphFocusPicker
          chapterNumber={chapterNumber}
          nodes={nodes}
          edges={edges}
          characters={characters}
          selectedIds={selectedIds}
          onChange={onChange}
        />
        <div className="mt-4 flex justify-end border-t border-paper-line/60 pt-3">
          <ToolTip id="chapter.graphPickerDone">
            <button
              type="button"
              onClick={() => setPickerOpen(false)}
              className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800"
            >
              Done
            </button>
          </ToolTip>
        </div>
      </Modal>

      <CreatePlotFromBriefModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        projectId={projectId}
        chapterNumber={chapterNumber}
        characters={characters}
        graphNodes={nodes}
        graphEdges={edges ?? []}
        onCreated={handleNodeCreated}
      />
    </section>
  );
}
