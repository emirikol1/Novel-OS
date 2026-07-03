import { useRef, useState } from "react";
import { api, type EbookParsePreview } from "../api/client";
import Modal, { Field, fieldClass } from "./Modal";
import ToolTip from "./ToolTip";
import { useToast } from "./Toaster";
import { useBackgroundJob } from "../hooks/useBackgroundJob";

function formatWords(n: number): string {
  return n.toLocaleString();
}

export default function EbookImportModal({
  open,
  onClose,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  onImported?: (projectId: string) => void;
}) {
  const toast = useToast();
  const { watchBackgroundJob } = useBackgroundJob();
  const fileRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<EbookParsePreview | null>(null);
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("");
  const [author, setAuthor] = useState("");
  const [extractAi, setExtractAi] = useState(true);
  const [synthesize, setSynthesize] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [parsing, setParsing] = useState(false);

  function reset() {
    setPreview(null);
    setTitle("");
    setGenre("");
    setAuthor("");
    setExtractAi(true);
    setSynthesize(false);
    if (fileRef.current) fileRef.current.value = "";
  }

  function handleClose() {
    if (submitting || parsing) return;
    reset();
    onClose();
  }

  async function onFileSelected(file: File) {
    setParsing(true);
    setPreview(null);
    try {
      const result = await api.previewImportEbook(file);
      setPreview(result);
      setTitle(result.title);
      setAuthor(result.author);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
      if (fileRef.current) fileRef.current.value = "";
    } finally {
      setParsing(false);
    }
  }

  async function startImport(e: React.FormEvent) {
    e.preventDefault();
    if (!preview || !genre.trim()) return;
    setSubmitting(true);
    const resolvedTitle = title.trim() || preview.title || preview.filename;
    try {
      const job = await api.importEbook({
        upload_id: preview.upload_id,
        title: resolvedTitle,
        genre: genre.trim(),
        author: author.trim() || preview.author,
        no_extract: !extractAi,
        synthesize: extractAi && synthesize,
      });
      const projectId = job.project_id;
      if (!projectId) throw new Error("Import started without a project id");

      watchBackgroundJob(job.job_id, {
        label: "Ebook import",
        kind: "ebook-import",
        projectId,
        successMessage: extractAi
          ? `Ebook import complete — "${resolvedTitle}" is ready (chapters + AI extraction)`
          : `Ebook import complete — "${resolvedTitle}" is ready in your library`,
        onSuccess: () => onImported?.(projectId),
      });

      toast(
        extractAi
          ? `Importing "${resolvedTitle}" in the background (text + chunked AI extraction)…`
          : `Importing "${resolvedTitle}" in the background…`,
        "success",
      );
      reset();
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open={open} onClose={handleClose} title="Import ebook">
      <form onSubmit={startImport}>
        <p className="mb-4 text-[14px] leading-relaxed text-ink-muted">
          Upload a plain-text or EPUB file. Novel OS detects chapters, imports manuscript drafts,
          and can run the Archivist on each chapter in word-sized chunks via your local LLM.
          The import runs in the background — you can keep working elsewhere.
        </p>

        <Field label="Ebook file (.txt, .epub)">
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.text,.epub,text/plain,application/epub+zip"
            disabled={submitting || parsing}
            className={fieldClass}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void onFileSelected(file);
            }}
          />
        </Field>

        {parsing && (
          <p className="mb-4 text-[13px] text-ink-muted">Analyzing file structure…</p>
        )}

        {preview && (
          <div className="mb-5 rounded-xl border border-paper-line bg-paper-card/80 p-4">
            <p className="text-[12px] font-bold uppercase tracking-wider text-ink-muted">
              Detected structure
            </p>
            <ul className="mt-2 space-y-1 text-[13px] text-ink-muted">
              <li>
                <span className="font-medium text-ink-text">{preview.filename}</span>
                {" · "}
                {preview.chapters.length} chapter{preview.chapters.length === 1 ? "" : "s"}
                {" · "}
                {formatWords(preview.total_words)} words
              </li>
              <li>Split: {preview.split_strategy}</li>
            </ul>
            <div className="mt-3 max-h-36 overflow-y-auto rounded-lg border border-paper-line/80 bg-paper/60 p-2">
              {preview.chapters.map((ch) => (
                <div key={ch.number} className="flex justify-between gap-3 py-0.5 text-[12.5px]">
                  <span className="truncate text-ink-text">
                    {ch.number}. {ch.title || `Chapter ${ch.number}`}
                  </span>
                  <span className="shrink-0 text-ink-muted">{formatWords(ch.word_count)} w</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {preview && (
          <>
            <Field label="Title">
              <input
                className={fieldClass}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={submitting}
              />
            </Field>
            <Field label="Genre">
              <input
                className={fieldClass}
                value={genre}
                onChange={(e) => setGenre(e.target.value)}
                placeholder="e.g. Literary Fiction"
                disabled={submitting}
                required
              />
            </Field>
            <Field label="Author">
              <input
                className={fieldClass}
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
                disabled={submitting}
              />
            </Field>

            <label className="mb-3 flex cursor-pointer items-start gap-2.5 text-[13.5px] text-ink-text">
              <input
                type="checkbox"
                className="mt-1"
                checked={extractAi}
                onChange={(e) => setExtractAi(e.target.checked)}
                disabled={submitting}
              />
              <span>
                <strong>Extract cast, plot &amp; bible with AI</strong>
                <span className="mt-0.5 block text-[12.5px] font-normal text-ink-muted">
                  Long chapters are processed in ~6k-word chunks through your local LLM (LM Studio).
                </span>
              </span>
            </label>

            {extractAi && (
              <label className="mb-4 flex cursor-pointer items-center gap-2.5 text-[13.5px] text-ink-text">
                <input
                  type="checkbox"
                  checked={synthesize}
                  onChange={(e) => setSynthesize(e.target.checked)}
                  disabled={submitting}
                />
                <span>Also synthesize story outline after import</span>
              </label>
            )}
          </>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <ToolTip id="modal.cancel">
            <button
              type="button"
              onClick={handleClose}
              disabled={submitting || parsing}
              className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted transition-colors hover:bg-ink/5"
            >
              Cancel
            </button>
          </ToolTip>
          <ToolTip id="modal.ebookImport">
            <button
              type="submit"
              disabled={!preview || !genre.trim() || submitting || parsing}
              className="rounded-lg bg-ink px-5 py-2 text-[13.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40"
            >
              {submitting ? "Starting…" : "Import in background"}
            </button>
          </ToolTip>
        </div>
      </form>
    </Modal>
  );
}
