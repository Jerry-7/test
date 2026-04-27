import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import PlanDetailPage from "../routes/PlanDetailPage";

const planDetailClient = vi.hoisted(() => ({
  getPlan: vi.fn().mockResolvedValue({
    plan_id: "plan-1",
    source_goal: "learn runtime profiles",
    model_profile_id: "profile-1",
    model_profile_name: "OpenAI Main",
    provider: "openai",
    model_name: "gpt-5-mini",
    tasks: [],
  }),
  listModelProfiles: vi.fn().mockResolvedValue([
    { model_profile_id: "profile-1", name: "OpenAI Main" },
    { model_profile_id: "profile-2", name: "Qwen Backup" },
  ]),
  startRun: vi.fn().mockResolvedValue({
    run_id: "run-1",
    plan_id: "plan-1",
    model_profile_id: "profile-2",
    status: "running",
  }),
}));

vi.mock("../api/client", () => planDetailClient);

test("plan detail submits selected run profile when starting a run", async () => {
  render(
    <MemoryRouter initialEntries={["/plans/plan-1"]}>
      <Routes>
        <Route path="/plans/:planId" element={<PlanDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await waitFor(() => expect(screen.getByLabelText(/run profile/i)).toBeTruthy());
  fireEvent.change(screen.getByLabelText(/run profile/i), {
    target: { value: "profile-2" },
  });
  fireEvent.change(screen.getByLabelText(/max workers/i), {
    target: { value: "2" },
  });
  fireEvent.click(screen.getByRole("button", { name: /start run/i }));

  await waitFor(() => {
    expect(planDetailClient.startRun).toHaveBeenCalledWith({
      plan_id: "plan-1",
      profile_id: "profile-2",
      max_workers: 2,
    });
  });
});
