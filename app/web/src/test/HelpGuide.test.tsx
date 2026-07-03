import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import HelpGuide from "../routes/HelpGuide";

function renderHelp(path = "/help") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/help" element={<HelpGuide />} />
        <Route path="/help/:topic" element={<HelpGuide />} />
      </Routes>
    </MemoryRouter>,
  );
}

test("renders workflow overview and feature links", () => {
  renderHelp();

  expect(screen.getByRole("heading", { name: /from story arc to finished chapter/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /your first manuscript/i })).toBeInTheDocument();
  expect(screen.getByText(/The chapter outline is the bridge/i)).toBeInTheDocument();
  expect(
    screen.getAllByRole("link").some((link) => link.getAttribute("href") === "/help/story-bible"),
  ).toBe(true);
  expect(
    screen.getAllByRole("link").some((link) => link.getAttribute("href") === "/help/getting-started"),
  ).toBe(true);
});

test("renders getting started help page", () => {
  renderHelp("/help/getting-started");

  expect(screen.getByRole("heading", { name: /your first manuscript/i })).toBeInTheDocument();
  expect(screen.getByText(/Starter seed is minimal/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Back to Help/i })).toHaveAttribute("href", "/help");
});

test("renders a feature help page", () => {
  renderHelp("/help/plot-threads");

  expect(screen.getByRole("heading", { name: "Plot Threads" })).toBeInTheDocument();
  expect(screen.getByText(/Legacy arc list/i)).toBeInTheDocument();
  expect(screen.getByText(/Story Graph is the primary planning layer/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Back to Help/i })).toHaveAttribute("href", "/help");
});

test("renders prompt settings help page", () => {
  renderHelp("/help/prompt-settings");

  expect(screen.getByRole("heading", { name: "Prompt Settings" })).toBeInTheDocument();
  expect(screen.getByText(/current, recommended, or custom prompts/i)).toBeInTheDocument();
  expect(screen.getByText(/immutable output-contract guards/i)).toBeInTheDocument();
});
