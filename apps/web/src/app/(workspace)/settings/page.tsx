"use client";

import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";

export default function SettingsPage() {
  const { selectedModelId, selectedVoiceUri, speechVoices, t } = useWorkspace();
  const selectedVoice = speechVoices.find((voice) => voice.voiceURI === selectedVoiceUri);

  return (
    <section className="settings-stage">
      <div className="settings-card">
        <div className="placeholder-icon"><Icons.settings /></div>
        <p className="eyebrow">{t.settings}</p>
        <h1>{t.settingsTitle}</h1>
        <p className="placeholder-copy">{t.settingsDescription}</p>

        <div className="settings-grid">
          <Link className="settings-link-card" href="/settings/models">
            <Icons.spark />
            <span><strong>{t.modelsTitle}</strong><small>{selectedModelId ?? t.modelsUnavailable}</small></span>
          </Link>
          <Link className="settings-link-card" href="/settings/voice">
            <Icons.mic />
            <span><strong>{t.voiceSettingsTitle}</strong><small>{selectedVoice?.name ?? t.voiceNoVoices}</small></span>
          </Link>
        </div>

        <Link className="placeholder-action" href="/"><Icons.chat />{t.backToChat}</Link>
      </div>
    </section>
  );
}
