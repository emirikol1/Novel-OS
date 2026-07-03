import { api, type JobStatus } from "../api/client";

export function isCancelledJobMessage(error?: string | null): boolean {
  if (!error) return false;
  return error === "Cancelled"
    || error.includes("Removed from queue")
    || error.includes("QueueCancelledError");
}

export type JobPollResult =
  | { status: "done" }
  | { status: "cancelled" }
  | { status: "failed"; error: string };

const MAX_POLL_ERRORS = 3;

/** Poll until a background job finishes, is cancelled, or fails. */
export async function pollJobUntilSettled(jobId: string, intervalMs = 1500): Promise<JobPollResult> {
  let pollErrors = 0;
  let lastError = "Job failed";

  return new Promise((resolve) => {
    const timer = window.setInterval(async () => {
      try {
        const s: JobStatus = await api.getJob(jobId);
        pollErrors = 0;
        if (s.status === "running") return;
        window.clearInterval(timer);
        if (s.status === "done") resolve({ status: "done" });
        else if (isCancelledJobMessage(s.error)) resolve({ status: "cancelled" });
        else {
          lastError = s.error?.trim() || lastError;
          resolve({ status: "failed", error: lastError });
        }
      } catch (e) {
        pollErrors += 1;
        if (pollErrors < MAX_POLL_ERRORS) return;
        window.clearInterval(timer);
        resolve({
          status: "failed",
          error: e instanceof Error ? e.message : "Could not poll job status",
        });
      }
    }, intervalMs);
  });
}

/** @deprecated Use pollJobUntilSettled — kept for callers that expect throw-on-fail. */
export async function pollJob(jobId: string): Promise<void> {
  const result = await pollJobUntilSettled(jobId);
  if (result.status === "done") return;
  if (result.status === "cancelled") throw new JobCancelledError();
  throw new Error(result.error || "Job failed");
}

export class JobCancelledError extends Error {
  constructor() {
    super("Cancelled");
    this.name = "JobCancelledError";
  }
}

export function isJobCancelledError(error: unknown): boolean {
  return error instanceof JobCancelledError || (error instanceof Error && isCancelledJobMessage(error.message));
}
