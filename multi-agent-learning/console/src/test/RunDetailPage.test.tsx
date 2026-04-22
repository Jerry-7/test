import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import RunDetailPage from "../routes/RunDetailPage";

const { retryRun, getRunDetail } = vi.hoisted(() => ({
  retryRun: vi.fn().mockResolvedValue({ run_id: "run-2" }),
  getRunDetail: vi.fn().mockResolvedValue({
    run_id: "run-1",
    plan_id: "plan-1",
    status: "failed",
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
}));

vi.mock("../api/client", () => ({
  getRunDetail,
  retryRun,
  requestRunControl: vi.fn(),
}));

test("shows retry and disabled unsupported controls", async () => {
  render(
    <MemoryRouter initialEntries={["/runs/run-1"]}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await waitFor(() => expect(screen.getByText(/review failed/i)).toBeTruthy());

  fireEvent.click(screen.getByRole("button", { name: /retry run/i }));
  await waitFor(() => expect(retryRun).toHaveBeenCalledWith("run-1"));

  expect(
    (screen.getByRole("button", { name: /pause/i }) as HTMLButtonElement).disabled,
  ).toBe(true);
  expect(
    (screen.getByRole("button", { name: /cancel/i }) as HTMLButtonElement).disabled,
  ).toBe(true);
});
