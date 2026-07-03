import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import App, { routeAnimationKey } from "../App";
import * as client from "../api/client";

test("renders the app shell with the wordmark", async () => {
  vi.spyOn(client.api, "projects").mockResolvedValue([]);
  render(<App />);
  expect(screen.getByText(/Novel OS/i)).toBeInTheDocument();
});

test("keeps the route animation container stable between chapters", () => {
  expect(routeAnimationKey("/projects/example/chapters/1")).toBe("/projects/example/chapters");
  expect(routeAnimationKey("/projects/example/chapters/2")).toBe("/projects/example/chapters");
  expect(routeAnimationKey("/projects/example")).toBe("/projects/example");
});
