import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, vi } from "vitest";
import ToolTip, { HOVER_DELAY_MS } from "../components/ToolTip";
import ToolTipDock from "../components/ToolTipDock";
import { ToolTipProvider, DISMISS_DELAY_MS } from "../context/ToolTipContext";
import { getToolTip } from "../lib/toolRegistry";

function renderWithTooltips(ui: ReactElement) {
  return render(
    <ToolTipProvider>
      {ui}
      <ToolTipDock />
    </ToolTipProvider>,
  );
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
});

test("renders child unchanged", () => {
  renderWithTooltips(
    <ToolTip id="chapter.revise">
      <button type="button" data-testid="anchor">
        Revise
      </button>
    </ToolTip>,
  );
  const button = screen.getByTestId("anchor");
  expect(button).toHaveTextContent("Revise");
  expect(button).not.toHaveAttribute("aria-describedby");
});

test("shows tooltip content in dock after hover delay", async () => {
  const entry = getToolTip("chapter.revise");
  renderWithTooltips(
    <ToolTip id="chapter.revise">
      <button type="button">Revise</button>
    </ToolTip>,
  );

  fireEvent.mouseEnter(screen.getByRole("button", { name: "Revise" }));
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

  await vi.advanceTimersByTimeAsync(HOVER_DELAY_MS);

  await waitFor(() => {
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });

  const tooltip = screen.getByRole("tooltip");
  expect(tooltip).toHaveTextContent(entry.label);
  expect(tooltip).toHaveTextContent(entry.function);
  expect(tooltip).toHaveTextContent(entry.worksOn);
  expect(tooltip).toHaveTextContent(entry.modifies);
  expect(tooltip).toHaveTextContent(entry.workflow);
  expect(tooltip).toHaveTextContent("Function");
  expect(tooltip).toHaveTextContent("Works on");
  expect(tooltip).toHaveTextContent("Modifies");
  expect(tooltip).toHaveTextContent("Workflow");
});

test("hides tooltip on mouse leave after dismiss delay", async () => {
  renderWithTooltips(
    <ToolTip id="chapter.revise">
      <button type="button">Revise</button>
    </ToolTip>,
  );

  const button = screen.getByRole("button", { name: "Revise" });
  fireEvent.mouseEnter(button);
  await vi.advanceTimersByTimeAsync(HOVER_DELAY_MS);

  await waitFor(() => {
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });

  fireEvent.mouseLeave(button);
  expect(screen.getByRole("tooltip")).toBeInTheDocument();

  await vi.advanceTimersByTimeAsync(DISMISS_DELAY_MS);
  await waitFor(() => {
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
});

test("tooltip dock stays open while pointer moves from trigger to dock", async () => {
  renderWithTooltips(
    <ToolTip id="chapter.revise">
      <button type="button">Revise</button>
    </ToolTip>,
  );

  const button = screen.getByRole("button", { name: "Revise" });
  fireEvent.mouseEnter(button);
  await vi.advanceTimersByTimeAsync(HOVER_DELAY_MS);

  const tooltip = await screen.findByRole("tooltip");
  fireEvent.mouseLeave(button);
  fireEvent.mouseEnter(tooltip);

  await vi.advanceTimersByTimeAsync(DISMISS_DELAY_MS);
  expect(screen.getByRole("tooltip")).toBeInTheDocument();
});
