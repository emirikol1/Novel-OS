import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import SelectedGraphNodeChips from "../components/SelectedGraphNodeChips";
import { SAMPLE_GRAPH_NODES } from "../lib/storyGraph";

test("renders selected node chips sorted by title and removes on click", async () => {
  const onRemove = vi.fn();
  const user = userEvent.setup();
  render(
    <SelectedGraphNodeChips
      nodes={SAMPLE_GRAPH_NODES}
      selectedIds={["sg_sub2", "sg_main", "unknown_id"]}
      onRemove={onRemove}
    />,
  );

  const titles = screen.getAllByText(/The Heist|Inside man betrayal/).map((el) => el.textContent);
  expect(titles).toEqual(["Inside man betrayal", "The Heist"]);
  expect(screen.queryByText(/Vault alarm/i)).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /Remove The Heist from chapter/i }));
  expect(onRemove).toHaveBeenCalledWith("sg_main");
});
