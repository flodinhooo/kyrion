"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Icons } from "@/components/icons";
import {
  createBrowserSpeechRecognition,
  speechText,
  type BrowserSpeechRecognition,
} from "@/features/voice/browser-speech";
import type { Locale } from "@/lib/messages";

type VoiceStatus = "starting" | "listening" | "thinking" | "speaking" | "paused" | "error";

function lastCompletedSentenceEnd(text: string): number {
  const sentenceEnd = /[.!?](?:["')\]]+)?(?=\s|$)/g;
  let completedUntil = 0;
  for (const match of text.matchAll(sentenceEnd)) {
    completedUntil = (match.index ?? 0) + match[0].length;
  }
  return completedUntil;
}

type VoiceModeProps = {
  isStreaming: boolean;
  latestAssistantMessage: { id: string; content: string } | null;
  locale: Locale;
  selectedVoiceUri: string | null;
  speechRate: number;
  streamFailed: boolean;
  t: {
    voiceClose: string;
    voiceError: string;
    voiceListening: string;
    voiceMicrophoneExternal: string;
    voicePause: string;
    voicePaused: string;
    voiceResume: string;
    voiceSpeaking: string;
    voiceStart: string;
    voiceThinking: string;
    voiceResponding: string;
    voiceUnsupported: string;
  };
  onClose: () => void;
  onSubmit: (transcript: string) => Promise<void>;
};

export function VoiceMode({
  isStreaming,
  latestAssistantMessage,
  locale,
  selectedVoiceUri,
  speechRate,
  streamFailed,
  t,
  onClose,
  onSubmit,
}: VoiceModeProps) {
  const [status, setStatus] = useState<VoiceStatus>("starting");
  const [transcript, setTranscript] = useState("");
  const [spokenRange, setSpokenRange] = useState({ start: 0, end: 0 });
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const recognition = useRef<BrowserSpeechRecognition | null>(null);
  const currentWord = useRef<HTMLElement | null>(null);
  const active = useRef(true);
  const paused = useRef(false);
  const pendingResponse = useRef(false);
  const handledAssistantId = useRef(latestAssistantMessage?.id ?? null);
  const queuedUntil = useRef(0);
  const queuedUtterances = useRef(0);
  const responseComplete = useRef(false);
  const startListeningRef = useRef<() => void>(() => undefined);
  const submitRef = useRef(onSubmit);
  const closeRef = useRef(onClose);

  useEffect(() => {
    submitRef.current = onSubmit;
    closeRef.current = onClose;
  }, [onClose, onSubmit]);

  useEffect(() => {
    if (status === "speaking") {
      currentWord.current?.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, [spokenRange, status]);

  const startListening = useCallback(() => {
    if (!active.current || paused.current || pendingResponse.current) return;
    window.speechSynthesis.cancel();

    const nextRecognition = createBrowserSpeechRecognition();
    if (!nextRecognition) {
      setStatus("error");
      setErrorMessage(t.voiceUnsupported);
      return;
    }

    let submitted = false;
    let failed = false;
    nextRecognition.lang = locale === "de" ? "de-DE" : "en-US";
    nextRecognition.continuous = false;
    nextRecognition.interimResults = true;
    nextRecognition.onstart = () => {
      setStatus("listening");
      setErrorMessage(null);
    };
    nextRecognition.onresult = (event) => {
      let currentTranscript = "";
      let finalTranscript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results[index];
        const text = result?.[0]?.transcript ?? "";
        currentTranscript += text;
        if (index >= event.resultIndex && result?.isFinal) finalTranscript += text;
      }
      setTranscript(currentTranscript.trim());

      const content = finalTranscript.trim();
      if (!content || submitted) return;
      submitted = true;
      pendingResponse.current = true;
      responseComplete.current = false;
      queuedUntil.current = 0;
      queuedUtterances.current = 0;
      setStatus("thinking");
      nextRecognition.stop();
      void submitRef.current(content);
    };
    nextRecognition.onerror = (event) => {
      if (event.error === "aborted" || !active.current || paused.current) return;
      failed = true;
      setStatus("error");
      setErrorMessage(t.voiceError);
    };
    nextRecognition.onend = () => {
      if (recognition.current === nextRecognition) recognition.current = null;
      if (!submitted && !failed && active.current && !paused.current && !pendingResponse.current) {
        window.setTimeout(() => startListeningRef.current(), 250);
      }
    };
    recognition.current = nextRecognition;
    nextRecognition.start();
  }, [locale, t.voiceError, t.voiceUnsupported]);

  useEffect(() => {
    startListeningRef.current = startListening;
  }, [startListening]);

  useEffect(() => {
    active.current = true;
    const startTimer = window.setTimeout(startListening, 0);
    const closeOnEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") closeRef.current();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      active.current = false;
      window.clearTimeout(startTimer);
      recognition.current?.abort();
      window.speechSynthesis.cancel();
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [startListening]);

  useEffect(() => {
    if (!pendingResponse.current) return;

    if (streamFailed) {
      pendingResponse.current = false;
      window.speechSynthesis.cancel();
      queueMicrotask(() => {
        setStatus("error");
        setErrorMessage(t.voiceError);
      });
      return;
    }

    if (!latestAssistantMessage?.content) {
      if (isStreaming && !window.speechSynthesis.speaking) queueMicrotask(() => setStatus("thinking"));
      return;
    }

    if (latestAssistantMessage.id !== handledAssistantId.current) {
      handledAssistantId.current = latestAssistantMessage.id;
      queuedUntil.current = 0;
      queuedUtterances.current = 0;
      responseComplete.current = false;
    }

    const completeText = speechText(latestAssistantMessage.content);
    queueMicrotask(() => setTranscript(completeText));
    if (isStreaming && !window.speechSynthesis.speaking && queuedUtterances.current === 0) {
      queueMicrotask(() => setStatus("thinking"));
    }

    responseComplete.current = !isStreaming;
    const speakUntil = isStreaming ? lastCompletedSentenceEnd(completeText) : completeText.length;
    if (paused.current || speakUntil <= queuedUntil.current) {
      if (!isStreaming && queuedUtterances.current === 0) {
        pendingResponse.current = false;
        queueMicrotask(() => setTranscript(""));
        startListeningRef.current();
      }
      return;
    }

    const chunkStart = queuedUntil.current;
    const chunk = completeText.slice(chunkStart, speakUntil).trim();
    queuedUntil.current = speakUntil;
    if (!chunk) return;

    const leadingWhitespace = completeText.slice(chunkStart, speakUntil).indexOf(chunk);
    const globalOffset = chunkStart + Math.max(leadingWhitespace, 0);
    const utterance = new SpeechSynthesisUtterance(chunk);
    utterance.lang = locale === "de" ? "de-DE" : "en-US";
    utterance.rate = speechRate;
    utterance.voice = window.speechSynthesis.getVoices().find((voice) =>
      voice.voiceURI === selectedVoiceUri,
    ) ?? window.speechSynthesis.getVoices().find((voice) =>
      voice.lang.toLowerCase().startsWith(locale),
    ) ?? null;
    queuedUtterances.current += 1;
    utterance.onstart = () => {
      setStatus("speaking");
      setSpokenRange({ start: globalOffset, end: globalOffset + 1 });
    };
    utterance.onboundary = (event) => {
      if (event.name !== "word") return;
      setSpokenRange({
        start: globalOffset + event.charIndex,
        end: globalOffset + event.charIndex + Math.max(event.charLength, 1),
      });
    };
    utterance.onend = () => {
      queuedUtterances.current = Math.max(0, queuedUtterances.current - 1);
      if (!responseComplete.current || queuedUtterances.current > 0) return;
      pendingResponse.current = false;
      setTranscript("");
      setSpokenRange({ start: 0, end: 0 });
      startListeningRef.current();
    };
    utterance.onerror = () => {
      queuedUtterances.current = Math.max(0, queuedUtterances.current - 1);
      if (!active.current || paused.current) return;
      setStatus("error");
      setErrorMessage(t.voiceError);
    };
    window.speechSynthesis.speak(utterance);
  }, [
    isStreaming,
    latestAssistantMessage,
    locale,
    selectedVoiceUri,
    speechRate,
    streamFailed,
    t.voiceError,
  ]);

  function toggleListening(): void {
    if (paused.current) {
      paused.current = false;
      setTranscript("");
      startListeningRef.current();
      return;
    }
    paused.current = true;
    recognition.current?.abort();
    window.speechSynthesis.cancel();
    setStatus("paused");
  }

  const statusText = status === "listening" ? t.voiceListening
    : status === "thinking" && latestAssistantMessage?.content ? t.voiceResponding
      : status === "thinking" ? t.voiceThinking
      : status === "speaking" ? t.voiceSpeaking
        : status === "paused" ? t.voicePaused
          : status === "error" ? errorMessage ?? t.voiceError
            : t.voiceStart;

  return (
    <div className={`voice-mode voice-${status}`} role="dialog" aria-modal="true" aria-label={statusText}>
      <button className="voice-close" type="button" aria-label={t.voiceClose} onClick={onClose} autoFocus>
        <Icons.close />
      </button>
      <div className="voice-mode-content">
        <div className="voice-orb" aria-hidden="true">
          <div className="orb-core" />
          <div className="orb-ring" />
          <span /><span /><span />
        </div>
        <p className="eyebrow">Velora Voice</p>
        <h2>{statusText}</h2>
        <div className="voice-transcript" aria-live="polite">
          {status === "speaking" && transcript ? <p>
            <span className="voice-spoken">{transcript.slice(0, spokenRange.start)}</span>
            <mark ref={currentWord}>{transcript.slice(spokenRange.start, spokenRange.end)}</mark>
            <span>{transcript.slice(spokenRange.end)}</span>
          </p> : <p>{transcript || "…"}</p>}
        </div>
        <p className="voice-privacy">{t.voiceMicrophoneExternal}</p>
      </div>
      <div className="voice-controls">
        <button type="button" onClick={toggleListening}>
          {status === "paused" ? <Icons.mic /> : <Icons.stop />}
          <span>{status === "paused" ? t.voiceResume : t.voicePause}</span>
        </button>
        <button type="button" onClick={onClose}><Icons.close /><span>{t.voiceClose}</span></button>
      </div>
    </div>
  );
}
