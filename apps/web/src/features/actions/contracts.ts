const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export type DeviceActionProposal = {
  type: "device";
  targetId: string;
  capability: "power.set" | "light.setBrightness" | "light.setColour";
  arguments: { on?: boolean; brightness?: number; hue?: number; saturation?: number };
};

export type WebActionRequest = {
  idempotencyKey: string;
  locale: "de" | "en";
  proposal: DeviceActionProposal;
  conversationId?: string;
};

export type ActionOutcome = {
  status: "succeeded" | "partially_succeeded" | "failed" | "rejected" | "confirmation_required";
  code: string;
  correlationId: string;
  capability: string | null;
  requested: number;
  succeeded: number;
  failed: number;
  targets: Array<{ targetId: string; displayName: string; status: string }>;
};

export function isWebActionRequest(value: unknown): value is WebActionRequest {
  if (!value || typeof value !== "object") return false;
  const request = value as Partial<WebActionRequest>;
  if (!uuid.test(request.idempotencyKey ?? "") || (request.locale !== "de" && request.locale !== "en")
    || (request.conversationId !== undefined && !uuid.test(request.conversationId))) return false;
  const proposal = request.proposal as Partial<DeviceActionProposal> | undefined;
  if (!proposal || proposal.type !== "device" || !uuid.test(proposal.targetId ?? "") || !proposal.arguments
    || typeof proposal.arguments !== "object") return false;
  const args = proposal.arguments;
  if (proposal.capability === "power.set") return typeof args.on === "boolean"
    && args.brightness === undefined && args.hue === undefined && args.saturation === undefined;
  if (proposal.capability === "light.setBrightness") return Number.isInteger(args.brightness)
    && (args.brightness ?? -1) >= 0 && (args.brightness ?? 101) <= 100
    && args.on === undefined && args.hue === undefined && args.saturation === undefined;
  return proposal.capability === "light.setColour" && Number.isInteger(args.hue)
    && (args.hue ?? -1) >= 0 && (args.hue ?? 361) <= 360 && Number.isInteger(args.saturation)
    && (args.saturation ?? -1) >= 0 && (args.saturation ?? 101) <= 100
    && args.on === undefined && args.brightness === undefined;
}

export function isActionOutcome(value: unknown): value is ActionOutcome {
  if (!value || typeof value !== "object") return false;
  const outcome = value as Partial<ActionOutcome>;
  return (outcome.status === "succeeded" || outcome.status === "partially_succeeded"
      || outcome.status === "failed" || outcome.status === "rejected"
      || outcome.status === "confirmation_required")
    && typeof outcome.code === "string" && uuid.test(outcome.correlationId ?? "")
    && (outcome.capability === null || typeof outcome.capability === "string")
    && typeof outcome.requested === "number" && typeof outcome.succeeded === "number"
    && typeof outcome.failed === "number" && Array.isArray(outcome.targets)
    && outcome.targets.every((target) => !!target && uuid.test(target.targetId)
      && typeof target.displayName === "string" && typeof target.status === "string");
}
