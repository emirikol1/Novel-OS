import { describe, expect, it, vi, afterEach } from "vitest";
import { waitForApiHealth, isNotFoundError, redirectOnProjectNotFound } from "../lib/apiHealth";

describe("apiHealth", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("isNotFoundError detects 404 messages", () => {
    expect(isNotFoundError(new Error("404 Not Found"))).toBe(true);
    expect(isNotFoundError(new Error("network fail"))).toBe(false);
  });

  it("waitForApiHealth resolves when health returns ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true }),
    );
    await expect(waitForApiHealth(2000)).resolves.toBe(true);
  });

  it("redirectOnProjectNotFound navigates to library on 404", () => {
    const navigate = vi.fn();
    const toast = vi.fn();
    const handled = redirectOnProjectNotFound(new Error("404 Not Found"), navigate, toast);
    expect(handled).toBe(true);
    expect(navigate).toHaveBeenCalledWith("/", { replace: true });
    expect(toast).toHaveBeenCalled();
  });
});
