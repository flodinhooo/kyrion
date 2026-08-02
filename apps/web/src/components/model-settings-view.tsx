"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";
import {
  isModelBenchmarkResult,
  type ModelBenchmarkResult,
} from "@/features/models/contracts";

function formatBytes(bytes: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: "gigabyte",
    maximumFractionDigits: 1,
  }).format(bytes / 1_000_000_000);
}

export function ModelSettingsView() {
  const { locale, modelCatalog, selectedModelId, selectModel, t } = useWorkspace();
  const [benchmarkResults, setBenchmarkResults] = useState<Record<string, ModelBenchmarkResult>>({});
  const [benchmarkErrors, setBenchmarkErrors] = useState<string[]>([]);
  const [benchmarkingModelId, setBenchmarkingModelId] = useState<string | null>(null);
  const abortController = useRef<AbortController | null>(null);

  useEffect(() => () => abortController.current?.abort(), []);

  const recommendedModelId = modelCatalog
    && Object.keys(benchmarkResults).length === modelCatalog.models.length
    ? [...Object.values(benchmarkResults)].sort((left, right) =>
        right.checksPassed - left.checksPassed
        || right.averageTokensPerSecond - left.averageTokensPerSecond
        || left.averageDurationMs - right.averageDurationMs,
      )[0]?.modelId
    : null;

  async function runBenchmark(): Promise<void> {
    if (!modelCatalog || benchmarkingModelId) return;
    const controller = new AbortController();
    abortController.current = controller;
    setBenchmarkResults({});
    setBenchmarkErrors([]);

    for (const model of modelCatalog.models) {
      if (controller.signal.aborted) break;
      setBenchmarkingModelId(model.id);
      try {
        const response = await fetch("/api/models/benchmark", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ modelId: model.id, locale }),
          signal: controller.signal,
        });
        const result: unknown = await response.json();
        if (!response.ok || !isModelBenchmarkResult(result)) {
          throw new Error("Invalid benchmark result");
        }
        setBenchmarkResults((current) => ({ ...current, [model.id]: result }));
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") break;
        setBenchmarkErrors((current) => [...current, model.id]);
      }
    }

    setBenchmarkingModelId(null);
    abortController.current = null;
  }

  function cancelBenchmark(): void {
    abortController.current?.abort();
    abortController.current = null;
    setBenchmarkingModelId(null);
  }

  function clearBenchmark(): void {
    setBenchmarkResults({});
    setBenchmarkErrors([]);
  }

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
        <>
          <section className="benchmark-panel" aria-labelledby="benchmark-title">
            <div>
              <p className="eyebrow">Local-first</p>
              <h2 id="benchmark-title">{t.benchmarkTitle}</h2>
              <p>{t.benchmarkDescription}</p>
              <small>{t.benchmarkPrivacy}</small>
            </div>
            <div className="benchmark-actions">
              {benchmarkingModelId ? (
                <button type="button" onClick={cancelBenchmark}>{t.benchmarkCancel}</button>
              ) : (
                <button type="button" onClick={() => void runBenchmark()}>{t.benchmarkStart}</button>
              )}
              {(Object.keys(benchmarkResults).length > 0 || benchmarkErrors.length > 0) && (
                <button className="secondary" type="button" onClick={clearBenchmark}>
                  {t.benchmarkClear}
                </button>
              )}
            </div>
            {benchmarkingModelId && (
              <p className="benchmark-progress" role="status">
                <span className="status-dot status-checking" />
                {t.benchmarkRunning}: {benchmarkingModelId}
              </p>
            )}
          </section>

          <div className="model-grid">
          {modelCatalog.models.map((model) => {
            const isSelected = model.id === selectedModelId;
            const isDefault = model.id === modelCatalog.defaultModelId;
            const isRecommended = model.id === recommendedModelId;
            const benchmark = benchmarkResults[model.id];
            const benchmarkFailed = benchmarkErrors.includes(model.id);
            return (
              <article className={`model-card ${isSelected ? "selected" : ""}`} key={model.id}>
                <div className="model-card-heading">
                  <div><Icons.spark /><h2>{model.label}</h2></div>
                  <div className="model-badges">
                    {isSelected && <span>{t.modelSelected}</span>}
                    {isDefault && <span>{t.modelDefault}</span>}
                    {isRecommended && <span>{t.benchmarkRecommended}</span>}
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
                {benchmarkingModelId === model.id && (
                  <p className="benchmark-model-state" role="status">{t.benchmarkTesting} …</p>
                )}
                {benchmark && (
                  <dl className="benchmark-results">
                    <div><dt>{t.benchmarkSpeed}</dt><dd>{benchmark.averageTokensPerSecond.toLocaleString(locale)} tok/s</dd></div>
                    <div><dt>{t.benchmarkDuration}</dt><dd>{(benchmark.averageDurationMs / 1_000).toLocaleString(locale, { maximumFractionDigits: 1 })} s</dd></div>
                    <div><dt>{t.benchmarkWarmup}</dt><dd>{(benchmark.warmupLoadMs / 1_000).toLocaleString(locale, { maximumFractionDigits: 1 })} s</dd></div>
                    <div><dt>{t.benchmarkChecks}</dt><dd>{benchmark.checksPassed}/{benchmark.promptCount}</dd></div>
                  </dl>
                )}
                {benchmarkFailed && <p className="stream-error" role="alert">{t.benchmarkError}</p>}
                <button type="button" disabled={isSelected} onClick={() => selectModel(model.id)}>
                  {isSelected ? t.modelSelected : t.selectModel}
                </button>
              </article>
            );
          })}
          </div>
        </>
      )}
    </section>
  );
}
