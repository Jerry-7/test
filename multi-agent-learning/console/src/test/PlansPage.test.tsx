import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import PlansPage from "../routes/PlansPage";

const plansClient = vi.hoisted(() => ({
  listPlans: vi.fn().mockResolvedValue([]),
  listModelProfiles: vi.fn().mockResolvedValue([
    { model_profile_id: "profile-1", name: "OpenAI Main" },
  ]),
  createPlan: vi.fn().mockResolvedValue({
    plan_id: "plan-1",
    source_goal: "learn runtime profiles",
    model_profile_id: "profile-1",
    tasks: [],
  }),
}));

vi.mock("../api/client", () => plansClient);

test("plans page submits selected profile when creating a plan", async () => {
  render(
    <MemoryRouter>
      <PlansPage />
    </MemoryRouter>,
  );

  await waitFor(() => expect(plansClient.listModelProfiles).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText(/goal/i), {
    target: { value: "learn runtime profiles" },
  });
  fireEvent.change(screen.getByLabelText(/model profile/i), {
    target: { value: "profile-1" },
  });
  fireEvent.click(screen.getByRole("button", { name: /create plan/i }));

  await waitFor(() => {
    expect(plansClient.createPlan).toHaveBeenCalledWith({
      task: "learn runtime profiles",
      profile_id: "profile-1",
    });
  });
});
