export type AiServiceStatus =
  | { status: "ready"; model: string }
  | { status: "unavailable" };

export function isAiServiceStatus(value: unknown): value is AiServiceStatus {
  if (!value || typeof value !== "object") return false;
  const status = value as Partial<AiServiceStatus>;
  return status.status === "unavailable"
    || (status.status === "ready" && typeof status.model === "string" && status.model.length > 0);
}
