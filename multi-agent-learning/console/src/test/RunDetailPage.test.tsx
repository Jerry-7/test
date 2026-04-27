import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import RunDetailPage from "../routes/RunDetailPage";

const { retryRun, getRunDetail, listModelProfiles } = vi.hoisted(() => ({
  retryRun: vi.fn().mockResolvedValue({ run_id: "run-2" }),
  getRunDetail: vi.fn().mockResolvedValue({
    run_id: "run-1",
    plan_id: "plan-1",
    status: "failed",
    model_profile_id: "profile-1",
    model_profile_name: "OpenAI Main",
    provider: "openai",
    model_name: "gpt-5-mini",
    tasks: [
      {
        task_id: "task-1",
        status: "failed",
        agent_name: "ReviewAgent",
        execution_task_id: "exec-1",
      },
    ],
    executions: [{ task_id: "exec-1", error: "review failed", output: "" }],
  }),
  listModelProfiles: vi.fn().mockResolvedValue([
    { model_profile_id: "profile-1", name: "OpenAI Main" },
    { model_profile_id: "profile-2", name: "Qwen Backup" },
  ]),
}));

vi.mock("../api/client", () => ({
  getRunDetail,
  listModelProfiles,
  retryRun,
  requestRunControl: vi.fn(),
}));

test("retry run defaults to original profile and can switch before retry", async () => {
  render(
    <MemoryRouter initialEntries={["/runs/run-1"]}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await waitFor(() => expect(screen.getByLabelText(/retry profile/i)).toBeTruthy());

  fireEvent.change(screen.getByLabelText(/retry profile/i), {
    target: { value: "profile-2" },
  });
  fireEvent.click(screen.getByRole("button", { name: /retry run/i }));

  await waitFor(() =>
    expect(retryRun).toHaveBeenCalledWith("run-1", {
      profile_id: "profile-2",
    }),
  );

  expect(
    (screen.getByRole("button", { name: /pause/i }) as HTMLButtonElement).disabled,
  ).toBe(true);
  expect(
    (screen.getByRole("button", { name: /cancel/i }) as HTMLButtonElement).disabled,
  ).toBe(true);
});
