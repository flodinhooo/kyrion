"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";

function voiceDisplayName(name: string): string {
  return name
    .replace(/\s+Online\s+\(Natural\)/i, "")
    .replace(/\s+-\s+.+$/, "")
    .trim();
}

export function VoiceSettingsView() {
  const {
    locale,
    selectedVoiceUri,
    selectVoice,
    setSpeechRate,
    speechRate,
    speechVoices,
    t,
  } = useWorkspace();
  const [previewingVoiceUri, setPreviewingVoiceUri] = useState<string | null>(null);
  const voices = speechVoices.filter((voice) =>
    voice.lang.toLowerCase().startsWith(locale),
  );

  useEffect(() => () => window.speechSynthesis.cancel(), []);

  function previewVoice(voiceUri: string): void {
    window.speechSynthesis.cancel();
    const voice = window.speechSynthesis.getVoices().find((item) =>
      item.voiceURI === voiceUri,
    );
    if (!voice) return;

    const utterance = new SpeechSynthesisUtterance(t.voicePreviewText);
    utterance.voice = voice;
    utterance.lang = voice.lang;
    utterance.rate = speechRate;
    utterance.onstart = () => setPreviewingVoiceUri(voiceUri);
    utterance.onend = () => setPreviewingVoiceUri(null);
    utterance.onerror = () => setPreviewingVoiceUri(null);
    window.speechSynthesis.speak(utterance);
  }

  return (
    <section className="models-stage">
      <div className="models-header">
        <div>
          <p className="eyebrow">Velora Voice</p>
          <h1>{t.voiceSettingsTitle}</h1>
          <p>{t.voiceSettingsDescription}</p>
        </div>
        <Link className="placeholder-action" href="/settings">{t.backToSettings}</Link>
      </div>

      <section className="voice-rate-panel">
        <div><strong>{t.voiceSpeed}</strong><small>{t.voiceSpeedDescription}</small></div>
        <input
          aria-label={t.voiceSpeed}
          type="range"
          min="0.7"
          max="1.3"
          step="0.05"
          value={speechRate}
          onChange={(event) => setSpeechRate(Number(event.target.value))}
        />
        <output>{speechRate.toLocaleString(locale, { maximumFractionDigits: 2 })}×</output>
      </section>

      <p className="voice-provider-note">{t.voiceProviderNote}</p>
      {voices.length === 0 ? (
        <p className="stream-error" role="alert">{t.voiceNoVoices}</p>
      ) : (
        <div className="voice-list">
          {voices.map((voice) => {
            const isSelected = voice.voiceURI === selectedVoiceUri;
            const isPreviewing = voice.voiceURI === previewingVoiceUri;
            return (
              <article className={`voice-card ${isSelected ? "selected" : ""}`} key={voice.voiceURI}>
                <div className="voice-card-heading">
                  <div className="voice-card-identity">
                    <span className="voice-card-icon"><Icons.mic /></span>
                    <div>
                      <h2 title={voice.name}>{voiceDisplayName(voice.name)}</h2>
                      <small>{voice.lang}</small>
                    </div>
                  </div>
                  <div className="voice-card-badges">
                    {voice.name.toLowerCase().includes("natural") && <span>{t.voiceNatural}</span>}
                    <span>{voice.localService ? t.voiceLocal : t.voiceOnline}</span>
                    {isSelected && <span className="selected">{t.voiceSelected}</span>}
                  </div>
                </div>
                <div className="voice-card-actions">
                  <button type="button" onClick={() => previewVoice(voice.voiceURI)}>
                    {isPreviewing ? t.voicePreviewing : t.voicePreview}
                  </button>
                  <button type="button" disabled={isSelected} onClick={() => selectVoice(voice.voiceURI)}>
                    {isSelected ? t.voiceSelected : t.voiceSelect}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
