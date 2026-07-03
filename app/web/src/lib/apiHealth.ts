const BASE = import.meta.env.VITE_API_BASE ?? "";

/** Poll until the API health endpoint responds (used after in-app restart). */
export async function waitForApiHealth(maxMs = 90_000): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    try {
      const resp = await fetch(`${BASE}/api/health`, { cache: "no-store" });
      if (resp.ok) return true;
    } catch {
      /* backend still starting */
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

export function isNotFoundError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return msg.includes("404") || msg.toLowerCase().includes("not found");
}

type ToastFn = (message: string, kind: "info" | "success" | "error") => void;
type NavigateFn = (to: string, opts?: { replace?: boolean }) => void;

const STALE_PROJECT_TOAST =
  "This project is no longer in your library. If you stashed it, restore it from the sidebar.";

/** Redirect away from a dead project URL instead of leaving a 404 banner on screen. */
export function redirectOnProjectNotFound(
  err: unknown,
  navigate: NavigateFn,
  toast: ToastFn,
): boolean {
  if (!isNotFoundError(err)) return false;
  toast(STALE_PROJECT_TOAST, "info");
  navigate("/", { replace: true });
  return true;
}

/** Chapter missing vs whole project missing — pick the right fallback route. */
export async function redirectOnChapterNotFound(
  err: unknown,
  projectId: string,
  navigate: NavigateFn,
  toast: ToastFn,
  fetchProject: (id: string) => Promise<unknown>,
): Promise<boolean> {
  if (!isNotFoundError(err)) return false;
  try {
    await fetchProject(projectId);
    toast("That chapter no longer exists.", "info");
    navigate(`/projects/${projectId}`, { replace: true });
  } catch (projectErr) {
    if (redirectOnProjectNotFound(projectErr, navigate, toast)) return true;
    toast(STALE_PROJECT_TOAST, "info");
    navigate("/", { replace: true });
  }
  return true;
}
