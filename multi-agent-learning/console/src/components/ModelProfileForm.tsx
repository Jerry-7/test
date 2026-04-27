import { useEffect, useState } from "react";

type ModelProfileFormValue = {
  name: string;
  provider: string;
  model_name: string;
  base_url?: string | null;
  thinking_mode: string;
  api_key: string;
};

const EMPTY_FORM: ModelProfileFormValue = {
  name: "",
  provider: "openai",
  model_name: "",
  base_url: "",
  thinking_mode: "default",
  api_key: "",
};

export default function ModelProfileForm({
  initialValue,
  onSubmit,
}: {
  initialValue?: Partial<ModelProfileFormValue>;
  onSubmit: (payload: ModelProfileFormValue) => Promise<void>;
}) {
  const [showSecret, setShowSecret] = useState(false);
  const [form, setForm] = useState<ModelProfileFormValue>({
    ...EMPTY_FORM,
    ...initialValue,
  });

  useEffect(() => {
    setForm({
      ...EMPTY_FORM,
      ...initialValue,
    });
    setShowSecret(false);
  }, [initialValue]);

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmit(form);
      }}
    >
      <label>
        Name
        <input
          aria-label="Name"
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
        />
      </label>
      <label>
        Provider
        <select
          aria-label="Provider"
          value={form.provider}
          onChange={(event) => setForm({ ...form, provider: event.target.value })}
        >
          <option value="openai">openai</option>
          <option value="openrouter">openrouter</option>
          <option value="qwen">qwen</option>
          <option value="glm">glm</option>
        </select>
      </label>
      <label>
        Model Name
        <input
          aria-label="Model Name"
          value={form.model_name}
          onChange={(event) =>
            setForm({ ...form, model_name: event.target.value })
          }
        />
      </label>
      <label>
        Base URL
        <input
          aria-label="Base URL"
          value={form.base_url ?? ""}
          onChange={(event) => setForm({ ...form, base_url: event.target.value })}
        />
      </label>
      <label>
        Thinking Mode
        <select
          aria-label="Thinking Mode"
          value={form.thinking_mode}
          onChange={(event) =>
            setForm({ ...form, thinking_mode: event.target.value })
          }
        >
          <option value="default">default</option>
          <option value="on">on</option>
          <option value="off">off</option>
        </select>
      </label>
      <label>
        API Key
        <input
          aria-label="API Key"
          type={showSecret ? "text" : "password"}
          value={form.api_key}
          onChange={(event) => setForm({ ...form, api_key: event.target.value })}
        />
      </label>
      <button type="button" onClick={() => setShowSecret((current) => !current)}>
        {showSecret ? "Hide" : "Show"}
      </button>
      <button type="submit">Save profile</button>
    </form>
  );
}
