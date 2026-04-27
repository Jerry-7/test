import { useEffect, useState } from "react";

import ModelProfileForm from "../components/ModelProfileForm";
import {
  createModelProfile,
  deleteModelProfile,
  duplicateModelProfile,
  getModelProfile,
  listModelProfiles,
  updateModelProfile,
} from "../api/client";

type ModelProfileRecord = {
  model_profile_id: string;
  name: string;
  provider: string;
  model_name: string;
  base_url?: string | null;
  thinking_mode: string;
  api_key?: string;
  api_key_hint?: string;
};

export default function ModelProfilesPage() {
  const [profiles, setProfiles] = useState<ModelProfileRecord[]>([]);
  const [editing, setEditing] = useState<ModelProfileRecord | null>(null);

  async function refresh() {
    const nextProfiles = await listModelProfiles();
    setProfiles(nextProfiles);
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <section>
      <h1>Model Profiles</h1>
      <ModelProfileForm
        initialValue={editing ?? undefined}
        onSubmit={async (payload) => {
          if (editing?.model_profile_id) {
            await updateModelProfile(editing.model_profile_id, payload);
          } else {
            await createModelProfile(payload);
          }
          setEditing(null);
          await refresh();
        }}
      />
      <ul>
        {profiles.map((profile) => (
          <li key={profile.model_profile_id}>
            {profile.name} - {profile.provider} - {profile.model_name} -{" "}
            {profile.api_key_hint}
            <button
              onClick={async () =>
                setEditing(await getModelProfile(profile.model_profile_id))
              }
            >
              Edit
            </button>
            <button
              onClick={async () => {
                await duplicateModelProfile(profile.model_profile_id);
                await refresh();
              }}
            >
              Duplicate
            </button>
            <button
              onClick={async () => {
                await deleteModelProfile(profile.model_profile_id);
                await refresh();
              }}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
