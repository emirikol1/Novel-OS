import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { api, type ProjectSummary } from "../api/client";
import ProjectCard from "../components/ProjectCard";
import Modal, { Field, fieldClass } from "../components/Modal";
import EbookImportModal from "../components/EbookImportModal";
import { useToast } from "../components/Toaster";
import { runningBackgroundJobs, useBackgroundJob } from "../hooks/useBackgroundJob";
import PanelToggle from "../components/PanelToggle";
import ToolTip from "../components/ToolTip";
import { notifyStashChanged } from "../components/StashPanel";
import { useLayoutPrefs } from "../context/LayoutPrefs";

const grid = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } };
const card = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const } },
};

export default function ProjectsList() {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [ebookOpen, setEbookOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const toast = useToast();
  const { showLibrary, toggleLibrary } = useLayoutPrefs();
  useBackgroundJob();
  const ebookImports = runningBackgroundJobs().filter((j) => j.kind === "ebook-import");

  const reload = useCallback(() => {
    api.projects().then(setProjects).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  async function deleteProject(p: ProjectSummary) {
    try {
      await api.deleteProject(p.id);
      toast(`Deleted "${p.title}"`, "success");
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  async function stashProject(p: ProjectSummary) {
    try {
      await api.stashProject(p.id);
      toast(`Stashed "${p.title}"`, "success");
      reload();
      notifyStashChanged();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  async function importProject(file: File) {
    setImporting(true);
    try {
      const p = await api.importProjectPackage(file);
      toast(`Imported "${p.title}"`, "success");
      reload();
      navigate(`/projects/${p.id}`);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setImporting(false);
      if (importRef.current) importRef.current.value = "";
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-10 py-12">
      <input
        ref={importRef}
        type="file"
        accept=".zip,application/zip"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void importProject(file);
        }}
      />
      <header className="mb-10 flex items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-[12px] font-semibold uppercase tracking-[0.2em] text-amber-deep">
            Library
          </p>
          <h1 className="font-display text-[40px] font-semibold leading-none tracking-tight text-ink-text text-balance">
            Your manuscripts
          </h1>
          <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-ink-muted">
            Every project is a living workspace — outlines, drafts, characters and continuity,
            orchestrated by your agent pipeline.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <div className="flex overflow-hidden rounded-lg border border-paper-line">
            <ToolTip id="library.togglePanel">
              <PanelToggle on={showLibrary} onClick={toggleLibrary} label="Library" />
            </ToolTip>
          </div>
          <ToolTip id="library.help">
            <Link
              to="/help"
              className="rounded-lg border border-paper-line px-5 py-2.5 text-[13.5px] font-semibold text-ink-text transition-colors hover:bg-ink/5"
            >
              Help
            </Link>
          </ToolTip>
          <ToolTip id="library.importEbook">
            <button
              type="button"
              onClick={() => setEbookOpen(true)}
              className="rounded-lg border border-paper-line px-5 py-2.5 text-[13.5px] font-semibold text-ink-text transition-colors hover:bg-ink/5"
            >
              Import ebook
            </button>
          </ToolTip>
          <ToolTip id="library.importProject">
            <button
              type="button"
              onClick={() => importRef.current?.click()}
              disabled={importing}
              className="rounded-lg border border-paper-line px-5 py-2.5 text-[13.5px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
            >
              {importing ? "Importing…" : "Import project"}
            </button>
          </ToolTip>
          <ToolTip id="library.newManuscript">
            <button
              onClick={() => setOpen(true)}
              className="rounded-lg bg-ink px-5 py-2.5 text-[13.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800"
            >
              + New Manuscript
            </button>
          </ToolTip>
        </div>
      </header>

      {ebookImports.length > 0 && (
        <div className="mb-6 rounded-lg border border-amber/30 bg-amber/10 px-5 py-3 text-[13.5px] text-ink-text">
          {ebookImports.length === 1
            ? `${ebookImports[0].label} running… you can open other projects while it finishes.`
            : `${ebookImports.length} ebook imports running in the background.`}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
          Failed to load projects: {error}
        </div>
      )}

      {!error && !projects && <SkeletonGrid />}

      {!error && projects && projects.length === 0 && (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-14 text-center">
          <p className="font-display text-[20px] text-ink-text">No manuscripts yet</p>
          <p className="mt-2 text-[14px] text-ink-muted">
            Create a manuscript, then paste chapters or use Generic Importer for cast and worldbuilding.
          </p>
          <ToolTip id="library.newManuscript">
            <button
              onClick={() => setOpen(true)}
              className="mt-5 rounded-lg bg-ink px-5 py-2.5 text-[13.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800"
            >
              + New Manuscript
            </button>
          </ToolTip>
        </div>
      )}

      {projects && projects.length > 0 && (
        <motion.div
          variants={grid}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3"
        >
          {projects.map((p) => (
            <motion.div key={p.id} variants={card}>
              <ProjectCard p={p} onDelete={deleteProject} onStash={stashProject} />
            </motion.div>
          ))}
        </motion.div>
      )}

      <NewProjectModal open={open} onClose={() => setOpen(false)} />
      <EbookImportModal
        open={ebookOpen}
        onClose={() => setEbookOpen(false)}
        onImported={() => reload()}
      />
    </div>
  );
}

function NewProjectModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("");
  const [author, setAuthor] = useState("");
  const [busy, setBusy] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      const p = await api.createProject({ title, genre, author });
      toast("Manuscript created", "success");
      navigate(`/projects/${p.id}`);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="New Manuscript">
      <form onSubmit={create}>
        <Field label="Title">
          <input
            autoFocus
            className={fieldClass}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. The Last Signal"
          />
        </Field>
        <Field label="Genre">
          <input
            className={fieldClass}
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
            placeholder="e.g. Sci-Fi Thriller"
          />
        </Field>
        <Field label="Author">
          <input
            className={fieldClass}
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            placeholder="Your name"
            autoComplete="name"
          />
        </Field>
        <div className="mt-6 flex justify-end gap-3">
          <ToolTip id="modal.cancel">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted transition-colors hover:bg-ink/5"
            >
              Cancel
            </button>
          </ToolTip>
          <ToolTip id="library.newManuscript">
            <button
              type="submit"
              disabled={!title.trim() || busy}
              className="rounded-lg bg-ink px-5 py-2 text-[13.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40"
            >
              {busy ? "Creating…" : "Create"}
            </button>
          </ToolTip>
        </div>
      </form>
    </Modal>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-44 animate-pulse rounded-xl border border-paper-line bg-paper-card/70"
        />
      ))}
    </div>
  );
}
