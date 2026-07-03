import { describe, expect, it } from "vitest";
import { activeJobBatchId, beginJobBatch, endJobBatch, runJobBatch } from "../lib/jobBatch";

describe("jobBatch", () => {
  it("scopes a batch id for nested job starts", async () => {
    expect(activeJobBatchId()).toBeNull();
    await runJobBatch(async () => {
      const id = activeJobBatchId();
      expect(id).toMatch(/^[a-f0-9]{32}$/);
    });
    expect(activeJobBatchId()).toBeNull();
  });

  it("clears batch id when endJobBatch is called", () => {
    beginJobBatch();
    expect(activeJobBatchId()).not.toBeNull();
    endJobBatch();
    expect(activeJobBatchId()).toBeNull();
  });
});
