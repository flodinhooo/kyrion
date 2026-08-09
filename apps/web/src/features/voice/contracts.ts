export type KyrionVoiceOption = {
  id: string;
  name: string;
  locale: string;
  gender: "female";
};

export type VoiceCatalog = {
  defaultVoiceId: string;
  voices: KyrionVoiceOption[];
};

export function isVoiceCatalog(value: unknown): value is VoiceCatalog {
  if (!value || typeof value !== "object") return false;
  const catalog = value as Partial<VoiceCatalog>;
  return typeof catalog.defaultVoiceId === "string"
    && Array.isArray(catalog.voices)
    && catalog.voices.every((voice) => voice
      && typeof voice.id === "string"
      && typeof voice.name === "string"
      && typeof voice.locale === "string"
      && voice.gender === "female");
}
