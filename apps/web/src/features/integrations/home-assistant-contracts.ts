export type HaStatus = { configured: boolean; status: string; reason?: string | null; lastSuccessAt?: string | null };
export type HaEntity = { key: string; name: string; state: string; supportsPower: boolean };
export type HaSource = { key: string; name: string; sourceRoom: string | null; entities: HaEntity[] };
export type HaPreview = { revision: number; devices: HaSource[] };
export type HaChoice = { key: string; entityKeys: string[]; allowControl: boolean; overrideRoom: boolean; roomId: string | null };
export type HaSelection = { revision: number; devices: HaChoice[] };
export type HaSelectionResult = { revision: number; selected: number; imported: number; reason: string | null };
export type HaRoom = { id: string; name: string };

function record(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === "object" && !Array.isArray(value); }
function text(value: unknown, max = 240): value is string { return typeof value === "string" && value.length <= max; }
function key(value: unknown): value is string { return typeof value === "string" && /^[a-f0-9]{64}$/.test(value); }
function uuid(value: unknown): value is string { return typeof value === "string" && /^[a-f0-9-]{36}$/i.test(value); }
function integer(value: unknown): value is number { return typeof value === "number" && Number.isSafeInteger(value) && value >= 0; }
function entity(value: unknown): value is HaEntity { return record(value) && key(value.key) && text(value.name) && text(value.state, 1024) && typeof value.supportsPower === "boolean"; }
function source(value: unknown): value is HaSource {
  return record(value) && key(value.key) && text(value.name) && (value.sourceRoom === null || text(value.sourceRoom)) &&
    Array.isArray(value.entities) && value.entities.length <= 2000 && value.entities.every(entity) && new Set(value.entities.map(item => item.key)).size === value.entities.length;
}
function choice(value: unknown): value is HaChoice {
  return record(value) && key(value.key) && Array.isArray(value.entityKeys) && value.entityKeys.length > 0 && value.entityKeys.length <= 2000 && value.entityKeys.every(key) &&
    new Set(value.entityKeys).size === value.entityKeys.length && typeof value.allowControl === "boolean" && typeof value.overrideRoom === "boolean" && (value.roomId === null || uuid(value.roomId));
}
export function isHaStatus(value: unknown): value is HaStatus {
  return record(value) && typeof value.configured === "boolean" && text(value.status, 40) && (value.reason == null || text(value.reason, 120)) &&
    (value.lastSuccessAt == null || typeof value.lastSuccessAt === "string" && Number.isFinite(Date.parse(value.lastSuccessAt)));
}
export function isHaPreview(value: unknown): value is HaPreview {
  return record(value) && integer(value.revision) && Array.isArray(value.devices) && value.devices.length <= 250 && value.devices.every(source) &&
    value.devices.reduce((total, item) => total + item.entities.length, 0) <= 2000 && new Set(value.devices.map(item => item.key)).size === value.devices.length;
}
export function isHaSelection(value: unknown): value is HaSelection {
  return record(value) && integer(value.revision) && Array.isArray(value.devices) && value.devices.length <= 250 && value.devices.every(choice) &&
    new Set(value.devices.map(item => item.key)).size === value.devices.length;
}
export function isHaSelectionResult(value: unknown): value is HaSelectionResult {
  return record(value) && integer(value.revision) && integer(value.selected) && integer(value.imported) && (value.reason === null || text(value.reason, 120));
}
export function isHaRooms(value: unknown): value is HaRoom[] {
  return Array.isArray(value) && value.length <= 1000 && value.every(item => record(item) && uuid(item.id) && text(item.name, 120));
}

export function changeHaEntities(choice: HaChoice, source: HaSource, entityKeys: string[]): HaChoice {
  const allowed = new Set(source.entities.map(entity => entity.key));
  if (entityKeys.some(key => !allowed.has(key)) || new Set(entityKeys).size !== entityKeys.length) throw new Error("HA_INVALID_SELECTION");
  const powerCount = source.entities.filter(entity => entityKeys.includes(entity.key) && entity.supportsPower).length;
  return { ...choice, entityKeys, allowControl: choice.allowControl && powerCount === 1 };
}
