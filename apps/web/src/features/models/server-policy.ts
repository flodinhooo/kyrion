import {isModelCatalog} from "./contracts";

export async function resolveChatModel(modelId: string | undefined, cloudConsent: boolean, signal?: AbortSignal, token?: string, task = "chat") {
  const response = await fetch(`${process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8000"}/v1/models`, {
    cache: "no-store",
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(10_000)]) : AbortSignal.timeout(10_000),
  });
  const value: unknown = await response.json();
  if (!response.ok || !isModelCatalog(value)) throw new Error("MODEL_UNAVAILABLE");
  let model = value.models.find(item => item.id === (modelId === "auto" ? value.defaultModelId : modelId ?? value.defaultModelId));
  if (!model) throw new Error("INVALID_REQUEST");
  if (model.enabled === false) throw new Error("MODEL_DISABLED");
  const cloud = model.provider !== undefined && model.provider !== "ollama";
  if (cloud && !cloudConsent) throw new Error("CLOUD_NOT_ALLOWED");
  if (model.available === false && modelId && modelId !== "auto") throw new Error(model.statusCode ?? "MODEL_UNAVAILABLE");
  const route = await fetch(`${process.env.CORE_SERVICE_URL ?? "http://127.0.0.1:8080"}/v1/ai/route`, {
    method: "POST",
    headers: {Authorization: `Bearer ${token ?? ""}`, "Content-Type": "application/json"},
    body: JSON.stringify({
      task, modelId: modelId === "auto" ? null : modelId ?? null,
      cloudConsent, consentProvider: cloud ? model.provider : null
    }),
    cache: "no-store",
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15_000)]) : AbortSignal.timeout(15_000),
  });
  const decision: unknown = await route.json();
  if (!route.ok) throw new Error(decision && typeof decision === "object" && "code" in decision && typeof decision.code === "string" ? decision.code : "MODEL_UNAVAILABLE");
  if (!decision || typeof decision !== "object" || !("model" in decision) || !decision.model || typeof decision.model !== "object"
    || !("id" in decision.model) || typeof decision.model.id !== "string") throw new Error("MODEL_UNAVAILABLE");
  const resolvedId = decision.model.id;
  model = value.models.find(item => item.id === resolvedId);
  if (!model) throw new Error("MODEL_UNAVAILABLE");
  return {model, cloud: model.local === false};
}
