"use client";

import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";

function formatBytes(bytes: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: "gigabyte",
    maximumFractionDigits: 1,
  }).format(bytes / 1_000_000_000);
}

export function ModelSettingsView() {
  const { locale, modelCatalog, selectedModelId, selectModel, t } = useWorkspace();

  return (
    <section className="models-stage">
      <div className="models-header">
        <div>
          <p className="eyebrow">{t.settings}</p>
          <h1>{t.modelsTitle}</h1>
          <p>{t.modelsDescription}</p>
        </div>
        <Link className="placeholder-action" href="/settings">{t.backToSettings}</Link>
      </div>

      {!modelCatalog ? (
        <p className="stream-error" role="alert">{t.modelsUnavailable}</p>
      ) : (
        <div className="model-grid">
          {modelCatalog.models.map((model) => {
            const isSelected = model.id === selectedModelId;
            const isDefault = model.id === modelCatalog.defaultModelId;
            return (
              <article className={`model-card ${isSelected ? "selected" : ""}`} key={model.id}>
                <div className="model-card-heading">
                  <div><Icons.spark /><h2>{model.label}</h2></div>
                  <div className="model-badges">
                    {isSelected && <span>{t.modelSelected}</span>}
                    {isDefault && <span>{t.modelDefault}</span>}
                  </div>
                </div>
                <dl>
                  <div><dt>{t.modelParameters}</dt><dd>{model.parameterSize}</dd></div>
                  <div><dt>{t.modelQuantization}</dt><dd>{model.quantization}</dd></div>
                  <div><dt>{t.modelSize}</dt><dd>{formatBytes(model.sizeBytes, locale)}</dd></div>
                  <div><dt>{t.modelContext}</dt><dd>{model.contextLength?.toLocaleString(locale) ?? "—"}</dd></div>
                </dl>
                <div className="capability-list">
                  {model.capabilities.length > 0
                    ? model.capabilities.map((capability) => <span key={capability}>{capability}</span>)
                    : <span>{t.modelCapabilitiesUnknown}</span>}
                </div>
                <button type="button" disabled={isSelected} onClick={() => selectModel(model.id)}>
                  {isSelected ? t.modelSelected : t.selectModel}
                </button>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
