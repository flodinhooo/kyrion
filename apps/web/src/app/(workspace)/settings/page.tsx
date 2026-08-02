"use client";

import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";

export default function SettingsPage() {
  const { modelCatalog, selectedModelId, selectModel, t } = useWorkspace();

  return (
    <section className="settings-stage">
      <div className="settings-card">
        <div className="placeholder-icon"><Icons.settings /></div>
        <p className="eyebrow">{t.settings}</p>
        <h1>{t.settingsTitle}</h1>
        <p className="placeholder-copy">{t.settingsDescription}</p>

        <div className="setting-group">
          <div>
            <label htmlFor="model-select">{t.modelSelection}</label>
            <p>{t.modelSelectionDescription}</p>
          </div>
          <select
            id="model-select"
            value={selectedModelId ?? ""}
            onChange={(event) => selectModel(event.target.value)}
            disabled={!modelCatalog || !selectedModelId}
          >
            {!modelCatalog && <option value="">{t.modelsUnavailable}</option>}
            {modelCatalog?.models.map((model) => (
              <option value={model.id} key={model.id}>{model.label}</option>
            ))}
          </select>
          <small>{t.modelStoredLocally}</small>
        </div>

        <Link className="placeholder-action" href="/"><Icons.chat />{t.backToChat}</Link>
      </div>
    </section>
  );
}
