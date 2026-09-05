export type BrowserSpeechRecognitionEvent = Event & {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      [index: number]: { transcript: string } | undefined;
    };
  };
};

export type BrowserSpeechRecognitionErrorEvent = Event & {
  error: string;
};

export interface BrowserSpeechRecognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onend: (() => void) | null;
  onerror: ((event: BrowserSpeechRecognitionErrorEvent) => void) | null;
  onresult: ((event: BrowserSpeechRecognitionEvent) => void) | null;
  onstart: (() => void) | null;
  abort: () => void;
  start: () => void;
  stop: () => void;
}

export type BrowserVoiceOption = {
  default: boolean;
  lang: string;
  localService: boolean;
  name: string;
  voiceURI: string;
};

type BrowserSpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

declare global {
  interface Window {
    SpeechRecognition?: BrowserSpeechRecognitionConstructor;
    webkitSpeechRecognition?: BrowserSpeechRecognitionConstructor;
  }
}

export function createBrowserSpeechRecognition(): BrowserSpeechRecognition | null {
  const Recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
  return Recognition ? new Recognition() : null;
}

export function availableBrowserVoices(): BrowserVoiceOption[] {
  return (window.speechSynthesis?.getVoices() ?? []).map((voice) => ({
    default: voice.default,
    lang: voice.lang,
    localService: voice.localService,
    name: voice.name,
    voiceURI: voice.voiceURI,
  }));
}

export function preferredBrowserVoice(
  voices: BrowserVoiceOption[],
  locale: "de" | "en",
): BrowserVoiceOption | null {
  const matchingVoices = voices.filter((voice) =>
    voice.lang.toLowerCase().startsWith(locale),
  );
  return matchingVoices.sort((left, right) => voiceScore(right) - voiceScore(left))[0] ?? null;
}

function voiceScore(voice: BrowserVoiceOption): number {
  const name = voice.name.toLowerCase();
  const isPreferredGermanVoice = voice.lang.toLowerCase() === "de-de"
    && name.includes("microsoft katja")
    && name.includes("natural");
  return (isPreferredGermanVoice ? 1_000 : 0)
    + (name.includes("natural") ? 100 : 0)
    + (name.includes("online") ? 50 : 0)
    + (voice.default ? 10 : 0)
    + (voice.localService ? 5 : 0);
}

export function speechText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)]\([^)]*\)/g, "$1")
    .replace(/^[#>*+-]+\s*/gm, "")
    .replace(/[*_~]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
