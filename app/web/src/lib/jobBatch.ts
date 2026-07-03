/** Groups concurrent job-start API calls so cancel stops the whole batch. */

let activeBatchId: string | null = null;

export function beginJobBatch(): string {
  activeBatchId = crypto.randomUUID().replace(/-/g, "");
  return activeBatchId;
}

export function endJobBatch(): void {
  activeBatchId = null;
}

export function activeJobBatchId(): string | null {
  return activeBatchId;
}

/** Run async work with a shared batch id on all job-start requests in this scope. */
export async function runJobBatch<T>(fn: () => Promise<T>): Promise<T> {
  beginJobBatch();
  try {
    return await fn();
  } finally {
    endJobBatch();
  }
}
