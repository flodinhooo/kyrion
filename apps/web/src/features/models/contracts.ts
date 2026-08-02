export type ModelOption = {
  id: string;
  label: string;
  sizeBytes: number;
  parameterSize: string;
  quantization: string;
  capabilities: string[];
  contextLength?: number | null;
};

export type ModelCatalog = {
  defaultModelId: string;
  models: ModelOption[];
};

export function isModelCatalog(value: unknown): value is ModelCatalog {
  if (!value || typeof value !== "object") return false;
  const catalog = value as Partial<ModelCatalog>;
  return typeof catalog.defaultModelId === "string"
    && catalog.defaultModelId.length > 0
    && Array.isArray(catalog.models)
    && catalog.models.length > 0
    && catalog.models.every((model) =>
      !!model
      && typeof model.id === "string"
      && model.id.length > 0
      && typeof model.label === "string"
      && model.label.length > 0
      && typeof model.sizeBytes === "number"
      && model.sizeBytes >= 0
      && typeof model.parameterSize === "string"
      && typeof model.quantization === "string"
      && Array.isArray(model.capabilities)
      && model.capabilities.every((capability) => typeof capability === "string")
      && (model.contextLength === undefined
        || model.contextLength === null
        || (typeof model.contextLength === "number" && model.contextLength > 0)),
    )
    && catalog.models.some((model) => model.id === catalog.defaultModelId);
}
