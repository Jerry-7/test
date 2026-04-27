import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import ModelProfilesPage from "../routes/ModelProfilesPage";

const client = vi.hoisted(() => ({
  listModelProfiles: vi.fn().mockResolvedValue([]),
  createModelProfile: vi.fn().mockResolvedValue({
    model_profile_id: "profile-1",
    name: "OpenAI Main",
    provider: "openai",
    model_name: "gpt-5-mini",
    base_url: null,
    thinking_mode: "default",
    api_key: "sk-openai-1234",
    api_key_hint: "****1234",
  }),
  deleteModelProfile: vi.fn().mockResolvedValue(undefined),
  duplicateModelProfile: vi.fn().mockResolvedValue(undefined),
  getModelProfile: vi.fn().mockResolvedValue(null),
  updateModelProfile: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../api/client", () => client);

test("creates a model profile and keeps api key hidden by default", async () => {
  render(
    <MemoryRouter initialEntries={["/model-profiles"]}>
      <Routes>
        <Route path="/model-profiles" element={<ModelProfilesPage />} />
      </Routes>
    </MemoryRouter>,
  );

  fireEvent.change(screen.getByLabelText(/^name$/i), {
    target: { value: "OpenAI Main" },
  });
  fireEvent.change(screen.getByLabelText(/provider/i), {
    target: { value: "openai" },
  });
  fireEvent.change(screen.getByLabelText(/model name/i), {
    target: { value: "gpt-5-mini" },
  });
  fireEvent.change(screen.getByLabelText(/api key/i), {
    target: { value: "sk-openai-1234" },
  });
  fireEvent.click(screen.getByRole("button", { name: /save profile/i }));

  await waitFor(() => expect(client.createModelProfile).toHaveBeenCalled());
  expect(screen.getByLabelText(/api key/i).getAttribute("type")).toBe("password");
});
