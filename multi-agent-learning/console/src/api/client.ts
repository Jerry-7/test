const API_BASE = "http://127.0.0.1:8000/api";

async function readJson(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json();
}

export function listModelProfiles() {
  return readJson("/model-profiles");
}

export function getModelProfile(profileId: string) {
  return readJson(`/model-profiles/${profileId}`);
}

export function createModelProfile(payload: {
  name: string;
  provider: string;
  model_name: string;
  base_url?: string | null;
  thinking_mode: string;
  api_key: string;
}) {
  return readJson("/model-profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function updateModelProfile(profileId: string, payload: Record<string, unknown>) {
  return readJson(`/model-profiles/${profileId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteModelProfile(profileId: string) {
  const response = await fetch(`${API_BASE}/model-profiles/${profileId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
}

export function duplicateModelProfile(profileId: string) {
  return readJson(`/model-profiles/${profileId}/duplicate`, {
    method: "POST",
  });
}

export function listPlans() {
  return readJson("/plans");
}

export function getPlan(planId: string) {
  return readJson(`/plans/${planId}`);
}

export function listRuns() {
  return readJson("/runs");
}

export function getRunDetail(runId: string) {
  return readJson(`/runs/${runId}`);
}

export function retryRun(runId: string) {
  return readJson(`/runs/${runId}/retry`, { method: "POST" });
}

export async function requestRunControl(
  runId: string,
  action: "pause" | "cancel",
) {
  const response = await fetch(`${API_BASE}/runs/${runId}/${action}`, {
    method: "POST",
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.message ?? `Run control failed: ${response.status}`);
  }
  return payload;
}
