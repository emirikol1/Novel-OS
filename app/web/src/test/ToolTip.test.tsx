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

test("does not wrap valid-element children in an extra span by default", () => {
  renderWithTooltips(
    <div data-testid="parent">
      <ToolTip id="chapter.revise">
        <button type="button" data-testid="anchor">
          Revise
        </button>
      </ToolTip>
    </div>,
  );
  const parent = screen.getByTestId("parent");
  const button = screen.getByTestId("anchor");
  // Anchor button should be a direct child of its layout parent — the ToolTip
  // wrapper must not insert an intermediate <span> that breaks flex/grid
  // hit-testing for NavLinks, breadcrumb links, panel toggles, etc.
  expect(button.parentElement).toBe(parent);
});

test("still wraps when caller supplies a layout className", () => {
  renderWithTooltips(
    <div data-testid="parent">
      <ToolTip id="chapter.revise" className="inline-flex h-7 items-center">
        <button type="button" data-testid="anchor">
          Revise
        </button>
      </ToolTip>
    </div>,
  );
  const button = screen.getByTestId("anchor");
  const wrapper = button.parentElement!;
  expect(wrapper.tagName).toBe("SPAN");
  expect(wrapper).toHaveClass("inline-flex", "h-7", "items-center");
});

test("clicks on the anchor still reach the child handler", async () => {
  const onClick = vi.fn();
  renderWithTooltips(
    <ToolTip id="chapter.revise">
      <button type="button" data-testid="anchor" onClick={onClick}>
        Revise
      </button>
    </ToolTip>,
  );
  fireEvent.click(screen.getByTestId("anchor"));
  expect(onClick).toHaveBeenCalledTimes(1);
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

test("shared tooltip ids only dismiss from the active trigger", async () => {
  renderWithTooltips(
    <div>
      <ToolTip id="chapter.revise">
        <button type="button">Revise A</button>
      </ToolTip>
      <ToolTip id="chapter.revise">
        <button type="button">Revise B</button>
      </ToolTip>
    </div>,
  );

  const activeButton = screen.getByRole("button", { name: "Revise A" });
  const inactiveButton = screen.getByRole("button", { name: "Revise B" });
  fireEvent.mouseEnter(activeButton);
  await vi.advanceTimersByTimeAsync(HOVER_DELAY_MS);

  await waitFor(() => {
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });
  expect(activeButton).toHaveAttribute("aria-describedby");
  expect(inactiveButton).not.toHaveAttribute("aria-describedby");

  fireEvent.mouseLeave(inactiveButton);
  await vi.advanceTimersByTimeAsync(DISMISS_DELAY_MS);
  expect(screen.getByRole("tooltip")).toBeInTheDocument();
});

test("clears tooltip when active trigger unmounts", async () => {
  function Fixture({ show }: { show: boolean }) {
    return (
      <ToolTipProvider>
        {show && (
          <ToolTip id="chapter.revise">
            <button type="button">Revise</button>
          </ToolTip>
        )}
        <ToolTipDock />
      </ToolTipProvider>
    );
  }

  const { rerender } = render(<Fixture show />);
  fireEvent.mouseEnter(screen.getByRole("button", { name: "Revise" }));
  await vi.advanceTimersByTimeAsync(HOVER_DELAY_MS);

  await waitFor(() => {
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });

  rerender(<Fixture show={false} />);
  await waitFor(() => {
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
});
