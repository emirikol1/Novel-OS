import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  mapImageUrl,
  type MapPinSummary,
  type ProjectMapDetail,
  type ProjectMapSummary,
} from "../api/client";
import DeleteButton from "./DeleteButton";
import Modal, { Field, fieldClass } from "./Modal";
import ToolTip from "./ToolTip";
import { useToast } from "./Toaster";
import { BIBLE_SECTION_META } from "../lib/mentions";
import {
  clampCoord,
  formatLoreReference,
  pointerToNormalized,
} from "../lib/mapPins";

function MapPinModal({
  projectId,
  mapId,
  pin,
  open,
  initialX,
  initialY,
  onClose,
  onSaved,
}: {
  projectId: string;
  mapId: string;
  pin: MapPinSummary | null;
  open: boolean;
  initialX: number;
  initialY: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const isEdit = pin != null;
  const [label, setLabel] = useState("");
  const [x, setX] = useState(0.5);
  const [y, setY] = useState(0.5);
  const [loreSection, setLoreSection] = useState("");
  const [loreLabel, setLoreLabel] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLabel(pin?.label ?? "");
    setX(pin?.x ?? initialX);
    setY(pin?.y ?? initialY);
    setLoreSection(pin?.lore_section ?? "");
    setLoreLabel(pin?.lore_label ?? "");
    setNotes(pin?.notes ?? "");
  }, [pin, initialX, initialY, open]);

  async function save() {
    if (!label.trim()) {
      toast("Pin label is required", "error");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        label: label.trim(),
        x: clampCoord(x),
        y: clampCoord(y),
        lore_section: loreSection.trim(),
        lore_label: loreLabel.trim(),
        notes: notes.trim(),
      };
      if (isEdit && pin) {
        await api.updateMapPin(projectId, mapId, pin.id, payload);
        toast("Pin updated", "success");
      } else {
        await api.createMapPin(projectId, mapId, payload);
        toast("Pin added", "success");
      }
      onSaved();
      onClose();
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={saving ? () => {} : onClose}
      title={isEdit ? "Edit Map Pin" : "Add Map Pin"}
      size="wide"
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <div className="space-y-1">
          <Field label="Label">
            <input className={fieldClass} value={label} onChange={(e) => setLabel(e.target.value)}
                   placeholder="e.g. Old Harbor" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="X (0–1)">
              <input className={fieldClass} type="number" min={0} max={1} step={0.01}
                     value={x} onChange={(e) => setX(clampCoord(Number(e.target.value)))} />
            </Field>
            <Field label="Y (0–1)">
              <input className={fieldClass} type="number" min={0} max={1} step={0.01}
                     value={y} onChange={(e) => setY(clampCoord(Number(e.target.value)))} />
            </Field>
          </div>
          <Field label="Lore section (optional)">
            <select className={fieldClass} value={loreSection} onChange={(e) => setLoreSection(e.target.value)}>
              <option value="">— none —</option>
              {BIBLE_SECTION_META.map((sec) => (
                <option key={sec.key} value={sec.key}>{sec.label}</option>
              ))}
            </select>
          </Field>
          <Field label="Lore / location label (optional)">
            <input className={fieldClass} value={loreLabel} onChange={(e) => setLoreLabel(e.target.value)}
                   placeholder="Story bible entry label" />
          </Field>
          <Field label="Notes">
            <textarea className={`${fieldClass} min-h-[72px]`} value={notes}
                      onChange={(e) => setNotes(e.target.value)} />
          </Field>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <ToolTip id="modal.cancel">
            <button type="button" onClick={onClose} disabled={saving}
                    className="rounded-lg px-4 py-2 text-[13px] text-ink-muted hover:bg-ink/5 disabled:opacity-50">
              Cancel
            </button>
          </ToolTip>
          <ToolTip id="codex.saveMapPin">
            <button type="submit" disabled={saving}
                    className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink disabled:opacity-50">
              {saving ? "Saving…" : isEdit ? "Save" : "Add pin"}
            </button>
          </ToolTip>
        </div>
      </form>
    </Modal>
  );
}

export default function MapPanel({
  projectId,
  onGoToBible,
}: {
  projectId: string;
  onGoToBible?: (section?: string) => void;
}) {
  const toast = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mapSurfaceRef = useRef<HTMLDivElement>(null);
  const dragPinRef = useRef<{ id: string; offsetX: number; offsetY: number } | null>(null);

  const [maps, setMaps] = useState<ProjectMapSummary[]>([]);
  const [activeMapId, setActiveMapId] = useState<string | null>(null);
  const [mapDetail, setMapDetail] = useState<ProjectMapDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [addMode, setAddMode] = useState(false);
  const [selectedPinId, setSelectedPinId] = useState<string | null>(null);
  const [pinModal, setPinModal] = useState<{
    pin: MapPinSummary | null;
    x: number;
    y: number;
  } | null>(null);

  const refreshMaps = useCallback(async () => {
    const list = await api.projectMaps(projectId);
    setMaps(list);
    if (!activeMapId && list.length > 0) {
      setActiveMapId(list[0].id);
    } else if (activeMapId && !list.some((m) => m.id === activeMapId)) {
      setActiveMapId(list[0]?.id ?? null);
    }
    return list;
  }, [projectId, activeMapId]);

  const refreshDetail = useCallback(async (mapId: string) => {
    const detail = await api.projectMap(projectId, mapId);
    setMapDetail(detail);
    return detail;
  }, [projectId]);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const list = await refreshMaps();
      const mapId = activeMapId ?? list[0]?.id;
      if (mapId) {
        await refreshDetail(mapId);
      } else {
        setMapDetail(null);
      }
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setLoading(false);
    }
  }, [refreshMaps, refreshDetail, activeMapId, toast]);

  useEffect(() => {
    reload().catch(() => setLoading(false));
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!activeMapId) return;
    refreshDetail(activeMapId).catch((e) => toast(String(e), "error"));
  }, [activeMapId, refreshDetail, toast]);

  const activeSummary = useMemo(
    () => maps.find((m) => m.id === activeMapId) ?? null,
    [maps, activeMapId],
  );

  const imageSrc = useMemo(() => {
    if (!activeMapId || !mapDetail?.image_url) return null;
    const stamp = mapDetail.updated_at ? `?v=${encodeURIComponent(mapDetail.updated_at)}` : "";
    return `${mapImageUrl(projectId, activeMapId)}${stamp}`;
  }, [projectId, activeMapId, mapDetail]);

  async function createMap() {
    try {
      const created = await api.createProjectMap(projectId, { name: maps.length === 0 ? "Main Map" : "Map" });
      await refreshMaps();
      setActiveMapId(created.id);
      toast("Map created", "success");
    } catch (e) {
      toast(String(e), "error");
    }
  }

  async function uploadImage(file: File) {
    if (!activeMapId) {
      toast("Create a map first", "error");
      return;
    }
    setUploading(true);
    try {
      await api.uploadMapImage(projectId, activeMapId, file);
      await reload();
      toast("Map image uploaded", "success");
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setUploading(false);
    }
  }

  async function deleteMap() {
    if (!activeMapId) return;
    try {
      await api.deleteProjectMap(projectId, activeMapId);
      setActiveMapId(null);
      setMapDetail(null);
      await refreshMaps();
      toast("Map deleted", "success");
    } catch (e) {
      toast(String(e), "error");
    }
  }

  function handleMapClick(e: React.MouseEvent) {
    if (!addMode || !mapSurfaceRef.current || !imageSrc) return;
    if ((e.target as HTMLElement).closest("[data-map-pin]")) return;
    const rect = mapSurfaceRef.current.getBoundingClientRect();
    const { x, y } = pointerToNormalized(e.clientX, e.clientY, rect);
    setPinModal({ pin: null, x, y });
    setAddMode(false);
  }

  function startDragPin(pin: MapPinSummary, e: React.PointerEvent) {
    if (!mapSurfaceRef.current) return;
    e.preventDefault();
    e.stopPropagation();
    const rect = mapSurfaceRef.current.getBoundingClientRect();
    const pinX = pin.x * rect.width;
    const pinY = pin.y * rect.height;
    dragPinRef.current = {
      id: pin.id,
      offsetX: e.clientX - rect.left - pinX,
      offsetY: e.clientY - rect.top - pinY,
    };
    setSelectedPinId(pin.id);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }

  async function moveDragPin(e: React.PointerEvent) {
    const drag = dragPinRef.current;
    if (!drag || !mapSurfaceRef.current || !activeMapId) return;
    const rect = mapSurfaceRef.current.getBoundingClientRect();
    const x = clampCoord((e.clientX - rect.left - drag.offsetX) / rect.width);
    const y = clampCoord((e.clientY - rect.top - drag.offsetY) / rect.height);
    setMapDetail((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        pins: prev.pins.map((p) => (p.id === drag.id ? { ...p, x, y } : p)),
      };
    });
  }

  async function endDragPin(e: React.PointerEvent) {
    const drag = dragPinRef.current;
    if (!drag || !activeMapId) return;
    dragPinRef.current = null;
    const pin = mapDetail?.pins.find((p) => p.id === drag.id);
    if (!pin) return;
    try {
      await api.updateMapPin(projectId, activeMapId, drag.id, { x: pin.x, y: pin.y });
    } catch (err) {
      toast(String(err), "error");
      if (activeMapId) refreshDetail(activeMapId).catch(() => {});
    }
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
  }

  async function deletePin(pin: MapPinSummary) {
    if (!activeMapId) return;
    try {
      await api.deleteMapPin(projectId, activeMapId, pin.id);
      setSelectedPinId(null);
      await refreshDetail(activeMapId);
      await refreshMaps();
      toast("Pin removed", "success");
    } catch (e) {
      toast(String(e), "error");
    }
  }

  const selectedPin = mapDetail?.pins.find((p) => p.id === selectedPinId) ?? null;

  if (loading && maps.length === 0) {
    return (
      <div className="rounded-xl border border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
        Loading maps…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {maps.length > 0 && (
          <select
            className="rounded-lg border border-paper-line bg-paper-card px-3 py-2 text-[13px]"
            value={activeMapId ?? ""}
            onChange={(e) => setActiveMapId(e.target.value || null)}
          >
            {maps.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.pin_count} pins)
              </option>
            ))}
          </select>
        )}
        <ToolTip id="codex.createMap">
          <button type="button" onClick={createMap}
                  className="rounded-lg border border-paper-line px-3.5 py-2 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5">
            + New Map
          </button>
        </ToolTip>
        {activeMapId && (
          <>
            <ToolTip id="codex.uploadMap">
              <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading}
                      className="rounded-lg border border-paper-line px-3.5 py-2 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-50">
                {uploading ? "Uploading…" : imageSrc ? "Replace image" : "Upload image"}
              </button>
            </ToolTip>
            <ToolTip id="codex.mapPin">
              <button type="button" onClick={() => setAddMode((v) => !v)} disabled={!imageSrc}
                      className={`rounded-lg border px-3.5 py-2 text-[12.5px] font-semibold transition-colors disabled:opacity-50 ${
                        addMode
                          ? "border-amber-deep bg-amber/10 text-amber-deep"
                          : "border-paper-line text-ink-text hover:bg-ink/5"
                      }`}>
                {addMode ? "Click map to place pin…" : "+ Add pin"}
              </button>
            </ToolTip>
            <DeleteButton
              label="Delete map"
              title="Delete map"
              message="Delete this map, its image, and all pins?"
              onConfirm={deleteMap}
              tipId="codex.deleteMap"
              className="rounded-lg border border-paper-line px-3.5 py-2 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5"
            />
          </>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) uploadImage(file);
            e.target.value = "";
          }}
        />
      </div>

      {!activeMapId ? (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
          No maps yet. Create a map, then upload an image and click to add location pins.
        </div>
      ) : !imageSrc ? (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
          Upload a map image for <span className="font-semibold text-ink-text">{activeSummary?.name}</span>.
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
          <div
            ref={mapSurfaceRef}
            className={`relative overflow-hidden rounded-xl border border-paper-line bg-ink/5 ${
              addMode ? "cursor-crosshair" : ""
            }`}
            onClick={handleMapClick}
          >
            <img src={imageSrc} alt={activeSummary?.name ?? "Project map"} className="block w-full select-none" draggable={false} />
            {mapDetail?.pins.map((pin) => (
              <ToolTip key={pin.id} id="codex.mapPin">
                <button
                  type="button"
                  data-map-pin
                  onPointerDown={(e) => startDragPin(pin, e)}
                  onPointerMove={moveDragPin}
                  onPointerUp={endDragPin}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedPinId(pin.id);
                  }}
                  onDoubleClick={(e) => {
                    e.stopPropagation();
                    setPinModal({ pin, x: pin.x, y: pin.y });
                  }}
                  className={`absolute z-10 -translate-x-1/2 -translate-y-full touch-none ${
                    selectedPinId === pin.id ? "z-20" : ""
                  }`}
                  style={{ left: `${pin.x * 100}%`, top: `${pin.y * 100}%` }}
                >
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full border-2 text-[10px] font-bold shadow-md ${
                      selectedPinId === pin.id
                        ? "border-amber-deep bg-amber text-on-ink"
                        : "border-paper-card bg-[var(--color-st-planned)] text-on-ink"
                    }`}
                  >
                    •
                  </span>
                  <span className="mt-0.5 block max-w-[120px] truncate rounded bg-paper-card/95 px-1.5 py-0.5 text-[10px] font-semibold text-ink-text shadow">
                    {pin.label}
                  </span>
                </button>
              </ToolTip>
            ))}
          </div>

          <aside className="rounded-xl border border-paper-line bg-paper-card p-4 shadow-[var(--shadow-paper)]">
            <h3 className="font-display text-[15px] font-semibold text-ink-text">Pins</h3>
            {selectedPin ? (
              <div className="mt-3 space-y-2 text-[13px]">
                <p className="font-semibold text-ink-text">{selectedPin.label}</p>
                <p className="text-ink-muted">
                  Position: {(selectedPin.x * 100).toFixed(1)}%, {(selectedPin.y * 100).toFixed(1)}%
                </p>
                {(selectedPin.lore_section || selectedPin.lore_label) && (
                  <p className="text-ink-muted">
                    Lore: {formatLoreReference(selectedPin.lore_section, selectedPin.lore_label)}
                  </p>
                )}
                {selectedPin.notes && <p className="whitespace-pre-wrap text-ink-text">{selectedPin.notes}</p>}
                <div className="flex flex-wrap gap-2 pt-2">
                  <ToolTip id="codex.editMapPin">
                    <button type="button"
                            onClick={() => setPinModal({ pin: selectedPin, x: selectedPin.x, y: selectedPin.y })}
                            className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] font-semibold hover:bg-ink/5">
                      Edit
                    </button>
                  </ToolTip>
                  {selectedPin.lore_section && onGoToBible && (
                    <ToolTip id="codex.storyBibleSection">
                      <button type="button"
                              onClick={() => onGoToBible(selectedPin.lore_section)}
                              className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] font-semibold hover:bg-ink/5">
                        Open bible section
                      </button>
                    </ToolTip>
                  )}
                  <DeleteButton
                    label={`Delete ${selectedPin.label}`}
                    title="Delete pin"
                    message={`Remove pin "${selectedPin.label}"?`}
                    onConfirm={() => deletePin(selectedPin)}
                    tipId="codex.deleteMapPin"
                    className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] font-semibold hover:bg-ink/5"
                  />
                </div>
              </div>
            ) : (
              <p className="mt-3 text-[13px] text-ink-muted">
                Click a pin to inspect it, drag to move, or double-click to edit. Use Add pin then click the map.
              </p>
            )}
            {mapDetail && mapDetail.pins.length > 0 && (
              <ul className="mt-4 max-h-64 space-y-1 overflow-y-auto border-t border-paper-line pt-3">
                {mapDetail.pins.map((pin) => (
                  <li key={pin.id}>
                    <ToolTip id="codex.mapPin">
                      <button type="button"
                              onClick={() => setSelectedPinId(pin.id)}
                              className={`w-full rounded-lg px-2 py-1.5 text-left text-[12.5px] ${
                                selectedPinId === pin.id ? "bg-amber/10 text-ink-text" : "text-ink-muted hover:bg-ink/5"
                              }`}>
                        {pin.label}
                      </button>
                    </ToolTip>
                  </li>
                ))}
              </ul>
            )}
          </aside>
        </div>
      )}

      {pinModal && activeMapId && (
        <MapPinModal
          projectId={projectId}
          mapId={activeMapId}
          pin={pinModal.pin}
          open
          initialX={pinModal.x}
          initialY={pinModal.y}
          onClose={() => setPinModal(null)}
          onSaved={async () => {
            if (activeMapId) {
              await refreshDetail(activeMapId);
              await refreshMaps();
            }
          }}
        />
      )}
    </div>
  );
}
