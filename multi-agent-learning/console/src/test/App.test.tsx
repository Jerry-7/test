import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "../App";

vi.mock("../api/client", () => ({
  listPlans: vi.fn().mockResolvedValue([
    { plan_id: "plan-1", source_goal: "Learn scheduling" },
  ]),
  listRuns: vi.fn().mockResolvedValue([
    { run_id: "run-1", plan_id: "plan-1", status: "running", max_workers: 1 },
  ]),
  listModelProfiles: vi.fn().mockResolvedValue([]),
  getPlan: vi.fn().mockResolvedValue({
    plan_id: "plan-1",
    source_goal: "Learn scheduling",
    tasks: [],
  }),
}));

test("dashboard shows recent plan and run summaries", async () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );

  await waitFor(() => {
    expect(screen.getByText(/learn scheduling/i)).toBeTruthy();
    expect(screen.getByText(/run-1/i)).toBeTruthy();
  });
});

test("app navigation shows model profiles tab", () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );

  expect(screen.getByRole("link", { name: /model profiles/i })).toBeTruthy();
});
