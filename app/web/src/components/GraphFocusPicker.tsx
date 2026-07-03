import { useMemo, useState } from "react";
import type {
  CharacterSummary,
  StoryGraphEdgeSummary,
  StoryGraphNodeSummary,
} from "../api/client";
import { fieldClass } from "./Modal";
import ToolTip from "./ToolTip";
import {
  buildContainsHierarchy,
  characterNameMap,
  collectBranchIds,
  filterMatchingNodes,
  lifespanLabel,
  mergeIds,
  nodeEligibleAtChapter,
  nodeMatchesFilters,
  partitionNodesByBriefEligibility,
  removeIds,
  type GraphFocusFilters,
} from "../lib/graphFocusPicker";
import { kindLabel, NODE_KINDS, NODE_STATUSES } from "../lib/storyGraph";
import { toggleId } from "../lib/chapterBrief";

type GraphFocusPickerProps = {
  chapterNumber: number;
  nodes: StoryGraphNodeSummary[];
  edges?: StoryGraphEdgeSummary[];
  characters: CharacterSummary[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
};

type NodeRowVariant = "in-effect" | "eligible" | "out-of-range";

function variantClass(variant: NodeRowVariant, selected: boolean): string {
  if (variant === "in-effect" || selected) {
    return "border-amber-deep/50 bg-amber/5";
  }
  if (variant === "eligible") {
    return "border-ink/15 bg-ink/[0.03]";
  }
  return "border-paper-line bg-paper-card opacity-60";
}

function NodeCheckboxRow({
  node,
  selected,
  depth = 0,
  characterNames,
  onToggle,
  branchAction,
  variant,
  disabled = false,
  chapterNumber,
}: {
  node: StoryGraphNodeSummary;
  selected: boolean;
  depth?: number;
  characterNames: Map<string, string>;
  onToggle: () => void;
  branchAction?: { label: string; onSelect: () => void };
  variant: NodeRowVariant;
  disabled?: boolean;
  chapterNumber: number;
}) {
  const linkedNames = node.linked_character_ids
    .map((id) => characterNames.get(id))
    .filter(Boolean);
  const outsideLifespan = selected && !nodeEligibleAtChapter(node, chapterNumber);

  return (
    <div
      className={`flex items-start gap-2 rounded-lg border px-2.5 py-2 ${variantClass(variant, selected)}`}
      style={{ marginLeft: depth > 0 ? `${depth * 14}px` : undefined }}
    >
      <label className={`flex min-w-0 flex-1 items-start gap-2 ${disabled ? "cursor-not-allowed" : "cursor-pointer"}`}>
        <input
          type="checkbox"
          checked={selected}
          disabled={disabled}
          onChange={onToggle}
          className="mt-0.5"
        />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="text-[12.5px] font-medium text-ink-text">{node.title}</span>
            <span className="rounded-full bg-ink/5 px-1.5 py-0.5 text-[10px] capitalize text-ink-muted">
              {kindLabel(node.kind)}
            </span>
            <span className="rounded-full bg-amber/10 px-1.5 py-0.5 text-[10px] capitalize text-ink-muted">
              {node.status}
            </span>
            {outsideLifespan && (
              <span className="rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] text-red-700">
                Outside lifespan
              </span>
            )}
          </span>
          <span className="mt-0.5 block text-[11px] text-ink-muted">{lifespanLabel(node)}</span>
          {node.description.trim() && (
            <span className="mt-0.5 block text-[11.5px] leading-snug text-ink-muted">
              {node.description}
            </span>
          )}
          {linkedNames.length > 0 && (
            <span className="mt-0.5 block text-[11px] text-ink-muted">
              Characters: {linkedNames.join(", ")}
            </span>
          )}
        </span>
      </label>
      {branchAction && (
        <ToolTip id="graph.focusPicker">
          <button
            type="button"
            onClick={branchAction.onSelect}
            className="shrink-0 text-[11px] font-semibold text-amber-deep hover:underline"
          >
            {branchAction.label}
          </button>
        </ToolTip>
      )}
    </div>
  );
}

function BranchList({
  nodeIds,
  nodesById,
  selectedSet,
  children,
  depth,
  characterNames,
  filters,
  onToggle,
  onSelectBranch,
  variant,
  chapterNumber,
}: {
  nodeIds: string[];
  nodesById: Map<string, StoryGraphNodeSummary>;
  selectedSet: Set<string>;
  children: Map<string, string[]>;
  depth: number;
  characterNames: Map<string, string>;
  filters: GraphFocusFilters;
  onToggle: (id: string) => void;
  onSelectBranch: (ids: string[]) => void;
  variant: NodeRowVariant;
  chapterNumber: number;
}) {
  return (
    <div className="space-y-1.5">
      {nodeIds.map((id) => {
        const node = nodesById.get(id);
        if (!node || !nodeMatchesFilters(node, filters, characterNames)) return null;
        const kids = children.get(id) ?? [];
        const hasBranch = kids.length > 0;
        const selected = selectedSet.has(id);
        const disabled = variant === "out-of-range";
        return (
          <div key={id} className="space-y-1.5">
            <NodeCheckboxRow
              node={node}
              selected={selected}
              depth={depth}
              characterNames={characterNames}
              onToggle={() => onToggle(id)}
              branchAction={
                hasBranch
                  ? {
                      label: "Select branch",
                      onSelect: () => onSelectBranch(collectBranchIds(id, children)),
                    }
                  : undefined
              }
              variant={variant}
              disabled={disabled}
              chapterNumber={chapterNumber}
            />
            {kids.length > 0 && (
              <BranchList
                nodeIds={kids}
                nodesById={nodesById}
                selectedSet={selectedSet}
                children={children}
                depth={depth + 1}
                characterNames={characterNames}
                filters={filters}
                onToggle={onToggle}
                onSelectBranch={onSelectBranch}
                variant={variant}
                chapterNumber={chapterNumber}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function FlatNodeList({
  nodes,
  selectedSet,
  characterNames,
  filters,
  onToggle,
  variant,
  chapterNumber,
}: {
  nodes: StoryGraphNodeSummary[];
  selectedSet: Set<string>;
  characterNames: Map<string, string>;
  filters: GraphFocusFilters;
  onToggle: (id: string) => void;
  variant: NodeRowVariant;
  chapterNumber: number;
}) {
  const visible = filterMatchingNodes(nodes, filters, characterNames);
  return (
    <div className="space-y-1.5">
      {visible.map((node) => (
        <NodeCheckboxRow
          key={node.id}
          node={node}
          selected={selectedSet.has(node.id)}
          characterNames={characterNames}
          onToggle={() => onToggle(node.id)}
          variant={variant}
          disabled={variant === "out-of-range"}
          chapterNumber={chapterNumber}
        />
      ))}
    </div>
  );
}

function SectionBlock({
  title,
  testId,
  nodes,
  edges,
  nodesById,
  selectedSet,
  characterNames,
  filters,
  onToggle,
  onSelectBranch,
  variant,
  chapterNumber,
  emptyMessage,
}: {
  title: string;
  testId: string;
  nodes: StoryGraphNodeSummary[];
  edges: StoryGraphEdgeSummary[];
  nodesById: Map<string, StoryGraphNodeSummary>;
  selectedSet: Set<string>;
  characterNames: Map<string, string>;
  filters: GraphFocusFilters;
  onToggle: (id: string) => void;
  onSelectBranch: (ids: string[]) => void;
  variant: NodeRowVariant;
  chapterNumber: number;
  emptyMessage: string;
}) {
  const hierarchy = useMemo(
    () => (edges.length > 0 ? buildContainsHierarchy(nodes, edges) : null),
    [nodes, edges],
  );
  const visibleCount = filterMatchingNodes(nodes, filters, characterNames).length;

  if (nodes.length === 0) {
    return (
      <div className="space-y-1.5" data-testid={testId}>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">{title}</p>
        <p className="text-[12px] text-ink-muted">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="space-y-1.5" data-testid={testId}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
        {title} ({visibleCount})
      </p>
      {visibleCount === 0 ? (
        <p className="text-[12px] text-ink-muted">No nodes match the current search and filters.</p>
      ) : hierarchy && hierarchy.roots.length > 0 ? (
        <>
          <BranchList
            nodeIds={hierarchy.roots}
            nodesById={nodesById}
            selectedSet={selectedSet}
            children={hierarchy.children}
            depth={0}
            characterNames={characterNames}
            filters={filters}
            onToggle={onToggle}
            onSelectBranch={onSelectBranch}
            variant={variant}
            chapterNumber={chapterNumber}
          />
          {hierarchy.orphans.length > 0 && (
            <div className="space-y-1.5 border-t border-paper-line/60 pt-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                Ungrouped
              </p>
              <BranchList
                nodeIds={hierarchy.orphans}
                nodesById={nodesById}
                selectedSet={selectedSet}
                children={hierarchy.children}
                depth={0}
                characterNames={characterNames}
                filters={filters}
                onToggle={onToggle}
                onSelectBranch={onSelectBranch}
                variant={variant}
                chapterNumber={chapterNumber}
              />
            </div>
          )}
        </>
      ) : (
        <FlatNodeList
          nodes={nodes}
          selectedSet={selectedSet}
          characterNames={characterNames}
          filters={filters}
          onToggle={onToggle}
          variant={variant}
          chapterNumber={chapterNumber}
        />
      )}
    </div>
  );
}

export default function GraphFocusPicker({
  chapterNumber,
  nodes,
  edges = [],
  characters,
  selectedIds,
  onChange,
}: GraphFocusPickerProps) {
  const [filters, setFilters] = useState<GraphFocusFilters>({
    search: "",
    kind: "all",
    status: "all",
  });
  const [showOutOfRange, setShowOutOfRange] = useState(false);

  const characterNames = useMemo(() => characterNameMap(characters), [characters]);
  const nodesById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const partition = useMemo(
    () => partitionNodesByBriefEligibility(nodes, chapterNumber, selectedIds),
    [nodes, chapterNumber, selectedIds],
  );

  const kindsInData = useMemo(
    () => [...new Set(nodes.map((n) => n.kind))].sort(),
    [nodes],
  );
  const statusesInData = useMemo(
    () => [...new Set(nodes.map((n) => n.status))].sort(),
    [nodes],
  );

  const hiddenSelected = useMemo(
    () =>
      selectedIds
        .map((id) => nodesById.get(id))
        .filter((node): node is StoryGraphNodeSummary => Boolean(node))
        .filter((node) => !nodeMatchesFilters(node, filters, characterNames)),
    [selectedIds, nodesById, filters, characterNames],
  );

  const hasActiveFilters =
    filters.search.trim() !== "" || filters.kind !== "all" || filters.status !== "all";

  function toggleNode(id: string) {
    onChange(toggleId(selectedIds, id));
  }

  function selectAllEligible() {
    const eligibleIds = partition.eligibleNotInEffect.map((node) => node.id);
    onChange(mergeIds(selectedIds, eligibleIds));
  }

  function clearInEffect() {
    onChange([]);
  }

  function clearResolved() {
    const resolvedIds = nodes.filter((n) => n.status === "resolved").map((n) => n.id);
    onChange(removeIds(selectedIds, resolvedIds));
  }

  return (
    <div className="space-y-3" data-testid="graph-focus-picker">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Chapter {chapterNumber} plot focus
        </p>
        <p className="text-[11px] text-ink-muted" data-testid="graph-focus-counts">
          {selectedIds.length} in effect · {partition.eligibleNotInEffect.length} eligible
          {partition.outOfRange.length > 0 ? ` · ${partition.outOfRange.length} out of range` : ""}
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <label className="min-w-[160px] flex-1">
          <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            Search
          </span>
          <input
            className={fieldClass}
            value={filters.search}
            onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
            placeholder="Title, description, kind, status, characters…"
            aria-label="Search story-graph nodes"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Kind
          <select
            className="min-w-[110px] rounded-lg border border-paper-line bg-paper-card px-2.5 py-1.5 text-[13px] font-normal normal-case text-ink-text"
            value={filters.kind}
            onChange={(e) => setFilters((f) => ({ ...f, kind: e.target.value }))}
            aria-label="Filter by kind"
          >
            <option value="all">All kinds</option>
            {(kindsInData.length ? kindsInData : [...NODE_KINDS]).map((kind) => (
              <option key={kind} value={kind}>
                {kindLabel(kind)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Status
          <select
            className="min-w-[110px] rounded-lg border border-paper-line bg-paper-card px-2.5 py-1.5 text-[13px] font-normal normal-case text-ink-text"
            value={filters.status}
            onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
            aria-label="Filter by status"
          >
            <option value="all">All statuses</option>
            {(statusesInData.length ? statusesInData : [...NODE_STATUSES]).map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        <ToolTip id="graph.focusPicker">
          <button
            type="button"
            onClick={selectAllEligible}
            disabled={partition.eligibleNotInEffect.length === 0}
            className="rounded-lg border border-paper-line px-2.5 py-1 text-[12px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40"
          >
            Select all eligible
          </button>
        </ToolTip>
        <ToolTip id="graph.focusPicker">
          <button
            type="button"
            onClick={clearInEffect}
            disabled={selectedIds.length === 0}
            className="rounded-lg border border-paper-line px-2.5 py-1 text-[12px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40"
          >
            Clear in effect
          </button>
        </ToolTip>
        <ToolTip id="graph.focusPicker">
          <button
            type="button"
            onClick={clearResolved}
            className="rounded-lg border border-paper-line px-2.5 py-1 text-[12px] font-semibold text-ink-text hover:bg-ink/5"
          >
            Clear resolved
          </button>
        </ToolTip>
      </div>

      {hiddenSelected.length > 0 && (
        <div className="space-y-1.5 rounded-lg border border-amber/25 bg-amber/5 p-2.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            In effect (hidden by filters)
          </p>
          <div className="space-y-1.5">
            {hiddenSelected.map((node) => (
              <NodeCheckboxRow
                key={node.id}
                node={node}
                selected
                characterNames={characterNames}
                onToggle={() => toggleNode(node.id)}
                variant="in-effect"
                chapterNumber={chapterNumber}
              />
            ))}
          </div>
        </div>
      )}

      <div className="max-h-[42vh] space-y-4 overflow-auto pr-1">
        <SectionBlock
          title="In effect (gold)"
          testId="graph-focus-in-effect"
          nodes={partition.inEffect}
          edges={edges}
          nodesById={nodesById}
          selectedSet={selectedSet}
          characterNames={characterNames}
          filters={filters}
          onToggle={toggleNode}
          onSelectBranch={(ids) => onChange(mergeIds(selectedIds, ids))}
          variant="in-effect"
          chapterNumber={chapterNumber}
          emptyMessage="No plots in effect — add eligible plots below."
        />

        <SectionBlock
          title="Eligible (silver)"
          testId="graph-focus-eligible"
          nodes={partition.eligibleNotInEffect}
          edges={edges}
          nodesById={nodesById}
          selectedSet={selectedSet}
          characterNames={characterNames}
          filters={filters}
          onToggle={toggleNode}
          onSelectBranch={(ids) => onChange(mergeIds(selectedIds, ids))}
          variant="eligible"
          chapterNumber={chapterNumber}
          emptyMessage={
            hasActiveFilters
              ? "No eligible plots match the current search and filters."
              : "All eligible plots are already in effect."
          }
        />

        {partition.outOfRange.length > 0 && (
          <div className="space-y-2 border-t border-paper-line/60 pt-2">
            <ToolTip id="graph.focusPicker">
              <button
                type="button"
                onClick={() => setShowOutOfRange((open) => !open)}
                className="text-[12px] font-semibold text-ink-text hover:underline"
              >
                {showOutOfRange ? "Hide" : "Show"} {partition.outOfRange.length} out-of-range plot
                {partition.outOfRange.length === 1 ? "" : "s"}
              </button>
            </ToolTip>
            {showOutOfRange && (
              <SectionBlock
                title="Out of range"
                testId="graph-focus-out-of-range"
                nodes={partition.outOfRange}
                edges={edges}
                nodesById={nodesById}
                selectedSet={selectedSet}
                characterNames={characterNames}
                filters={filters}
                onToggle={toggleNode}
                onSelectBranch={(ids) => onChange(mergeIds(selectedIds, ids))}
                variant="out-of-range"
                chapterNumber={chapterNumber}
                emptyMessage="No out-of-range plots."
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
