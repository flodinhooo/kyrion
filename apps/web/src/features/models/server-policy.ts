import {isModelCatalog} from "./contracts";

export async function resolveChatModel(modelId: string | undefined, cloudConsent: boolean, signal?: AbortSignal) {
  const response = await fetch(`${process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8000"}/v1/models`, {
    cache: "no-store",
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(10_000)]) : AbortSignal.timeout(10_000),
  });
  const value: unknown = await response.json();
  if (!response.ok || !isModelCatalog(value)) throw new Error("MODEL_UNAVAILABLE");
  const model = value.models.find(item => item.id === (modelId ?? value.defaultModelId));
  if (!model) throw new Error("INVALID_REQUEST");
  if (model.enabled === false) throw new Error("MODEL_DISABLED");
  const cloud = model.provider !== undefined && model.provider !== "ollama";
  if (cloud && !cloudConsent) throw new Error("CLOUD_NOT_ALLOWED");
  if (model.available === false) throw new Error(model.statusCode ?? "MODEL_UNAVAILABLE");
  return {model, cloud};
}
