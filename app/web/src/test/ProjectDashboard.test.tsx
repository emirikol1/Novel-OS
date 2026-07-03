import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { vi } from "vitest";
import ProjectDashboard from "../routes/ProjectDashboard";
import * as client from "../api/client";
import { TestProviders } from "./TestProviders";

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(client.api, "getRegeneratePreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getOutlinePreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getExpandPreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getParagraphsPreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getAlignmentPreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getRedraftPreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getChapterBeatCandidatesPreview").mockResolvedValue(null);
});

test("shows project title and chapter cards", async () => {
  vi.spyOn(client.api, "project").mockResolvedValue({
    id: "p", title: "My Novel", genre: "Drama", author: "A",
    chapter_count: 1, status: "in_progress", style: {},
  });
  vi.spyOn(client.api, "chapters").mockResolvedValue([
    { number: 1, title: "Opening", status: "drafted", word_count: 2300, pov: "Lena", pipeline_step: "drafted" },
  ]);
  vi.spyOn(client.api, "characters").mockResolvedValue([]);
  vi.spyOn(client.api, "plotThreads").mockResolvedValue([]);
  vi.spyOn(client.api, "timelineEvents").mockResolvedValue([]);
  vi.spyOn(client.api, "researchSparks").mockResolvedValue([]);
  vi.spyOn(client.api, "storyGraphNodes").mockResolvedValue([]);
  vi.spyOn(client.api, "storyGraphEdges").mockResolvedValue([]);
  render(
    <TestProviders>
      <MemoryRouter initialEntries={["/projects/p"]}>
        <Routes><Route path="/projects/:id" element={<ProjectDashboard />} /></Routes>
      </MemoryRouter>
    </TestProviders>,
  );
  expect(await screen.findByText("My Novel")).toBeInTheDocument();
  expect(screen.getByText("Opening")).toBeInTheDocument();
  expect(screen.getByLabelText("Draft")).toBeInTheDocument();
});

test("pipeline buckets open filtered chapter list", async () => {
  const user = userEvent.setup();
  vi.spyOn(client.api, "project").mockResolvedValue({
    id: "p", title: "My Novel", genre: "Drama", author: "A",
    chapter_count: 2, status: "in_progress", style: {},
  });
  vi.spyOn(client.api, "chapters").mockResolvedValue([
    { number: 1, title: "Opening", status: "drafted", word_count: 2300, pov: "Lena", pipeline_step: "drafted" },
    { number: 2, title: "Finale", status: "complete", word_count: 1800, pov: "Maro", pipeline_step: "final" },
  ]);
  vi.spyOn(client.api, "characters").mockResolvedValue([]);
  vi.spyOn(client.api, "plotThreads").mockResolvedValue([]);
  vi.spyOn(client.api, "timelineEvents").mockResolvedValue([]);
  vi.spyOn(client.api, "researchSparks").mockResolvedValue([]);
  vi.spyOn(client.api, "storyGraphNodes").mockResolvedValue([]);
  vi.spyOn(client.api, "storyGraphEdges").mockResolvedValue([]);
  render(
    <TestProviders>
      <MemoryRouter initialEntries={["/projects/p?tab=timeline"]}>
        <Routes><Route path="/projects/:id" element={<ProjectDashboard />} /></Routes>
      </MemoryRouter>
    </TestProviders>,
  );

  await screen.findByText("My Novel");
  await user.click(screen.getByRole("button", { name: /Show Draft chapters \(1\)/i }));

  expect(screen.getByRole("heading", { name: "Chapters" })).toBeInTheDocument();
  expect(screen.getByLabelText("Filter chapters by status")).toHaveValue("drafted");
  expect(screen.getByText("Opening")).toBeInTheDocument();
  expect(screen.queryByText("Finale")).not.toBeInTheDocument();
});

test("defers non-visible dashboard files and quick-loads selected tab data", async () => {
  const user = userEvent.setup();
  vi.spyOn(client.api, "project").mockResolvedValue({
    id: "p", title: "My Novel", genre: "Drama", author: "A",
    chapter_count: 1, status: "in_progress", style: {},
  });
  vi.spyOn(client.api, "chapters").mockResolvedValue([
    { number: 1, title: "Opening", status: "drafted", word_count: 2300, pov: "Lena", pipeline_step: "drafted" },
  ]);
  const characters = vi.spyOn(client.api, "characters").mockResolvedValue([]);
  const plotThreads = vi.spyOn(client.api, "plotThreads").mockResolvedValue([]);
  const timelineEvents = vi.spyOn(client.api, "timelineEvents").mockResolvedValue([]);
  const researchSparks = vi.spyOn(client.api, "researchSparks").mockResolvedValue([]);
  vi.spyOn(client.api, "storyGraphNodes").mockResolvedValue([]);
  vi.spyOn(client.api, "storyGraphEdges").mockResolvedValue([]);
  render(
    <TestProviders>
      <MemoryRouter initialEntries={["/projects/p"]}>
        <Routes><Route path="/projects/:id" element={<ProjectDashboard />} /></Routes>
      </MemoryRouter>
    </TestProviders>,
  );

  expect(await screen.findByText("My Novel")).toBeInTheDocument();
  expect(screen.getByText("Opening")).toBeInTheDocument();
  expect(characters).not.toHaveBeenCalled();
  expect(plotThreads).not.toHaveBeenCalled();
  expect(timelineEvents).not.toHaveBeenCalled();
  expect(researchSparks).not.toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: "Timeline" }));

  expect(characters).toHaveBeenCalledWith("p");
  expect(timelineEvents).toHaveBeenCalledWith("p");
  expect(plotThreads).not.toHaveBeenCalled();
  expect(researchSparks).not.toHaveBeenCalled();
});

test("opens review inbox tab and Mine All modal", async () => {
  const user = userEvent.setup();
  vi.spyOn(client.api, "project").mockResolvedValue({
    id: "p", title: "My Novel", genre: "Drama", author: "A",
    chapter_count: 1, status: "in_progress", style: {},
  });
  vi.spyOn(client.api, "chapters").mockResolvedValue([
    { number: 1, title: "Opening", status: "drafted", word_count: 2300, pov: "Lena", pipeline_step: "drafted" },
  ]);
  vi.spyOn(client.api, "reviewableChanges").mockResolvedValue([]);

  render(
    <TestProviders>
      <MemoryRouter initialEntries={["/projects/p"]}>
        <Routes><Route path="/projects/:id" element={<ProjectDashboard />} /></Routes>
      </MemoryRouter>
    </TestProviders>,
  );

  await screen.findByText("My Novel");
  await user.click(screen.getByRole("button", { name: "Review" }));

  expect(await screen.findByText("Reviewable Changes")).toBeInTheDocument();
  expect(client.api.reviewableChanges).toHaveBeenCalledWith("p");

  await user.click(screen.getByRole("button", { name: /Project Operations/i }));
  await user.click(screen.getByRole("button", { name: /Mine All/i }));

  expect(screen.getByRole("dialog", { name: "Mine All" })).toBeInTheDocument();
  expect(screen.getByText("Missing outlines")).toBeInTheDocument();
  expect(screen.getByText("Missing chapter briefs")).toBeInTheDocument();
  expect(screen.getByText("Everything")).toBeInTheDocument();
});
