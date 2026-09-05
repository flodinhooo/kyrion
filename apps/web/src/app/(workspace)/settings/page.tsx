"use client";

import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";

export default function SettingsPage() {
  const { selectedVoiceUri, speechVoices, textSize, setTextSize, t } = useWorkspace();
  const selectedVoice = speechVoices.find((voice) => voice.voiceURI === selectedVoiceUri);

  return (
    <section className="settings-stage">
      <div className="settings-card">
        <div className="placeholder-icon"><Icons.settings /></div>
        <p className="eyebrow">{t.settings}</p>
        <h1>{t.settingsTitle}</h1>
        <p className="placeholder-copy">{t.settingsDescription}</p>

        <div className="settings-grid">
          <div className="typography-setting">
            <div className="typography-setting-heading">
              <span className="typography-icon" aria-hidden="true">Aa</span>
              <span><strong>{t.textSize}</strong><small>{t.textSizeDescription}</small></span>
            </div>
            <div className="text-size-options" role="group" aria-label={t.textSize}>
              {(["standard", "comfortable", "large"] as const).map((size) => (
                <button className={textSize === size ? "selected" : ""} type="button" onClick={() => setTextSize(size)} key={size}>
                  <span className={`text-size-preview ${size}`}>Aa</span>
                  <small>{t[size === "standard" ? "textSizeStandard" : size === "comfortable" ? "textSizeComfortable" : "textSizeLarge"]}</small>
                </button>
              ))}
            </div>
            <p>{t.textSizeStoredLocally}</p>
          </div>
          <Link className="settings-link-card" href="/settings/models">
            <Icons.spark />
            <span><strong>{t.modelsTitle}</strong><small>{t.modelsDescription}</small></span>
          </Link>
          <Link className="settings-link-card" href="/settings/voice">
            <Icons.mic />
            <span><strong>{t.voiceSettingsTitle}</strong><small>{selectedVoice?.name ?? t.voiceNoVoices}</small></span>
          </Link>
          <Link className="settings-link-card" href="/settings/gateways">
            <Icons.shield />
            <span><strong>{t.gatewayTitle}</strong><small>{t.gatewaySettingsDescription}</small></span>
          </Link>
          <Link className="settings-link-card" href="/settings/services">
            <Icons.activity />
            <span><strong>{t.systemServicesTitle}</strong><small>{t.systemServicesSettingsDescription}</small></span>
          </Link>
          <Link className="settings-link-card" href="/knowledge">
            <Icons.book />
            <span><strong>{t.knowledgeTitle}</strong><small>{t.knowledgeDescription}</small></span>
          </Link>
        </div>

        <Link className="placeholder-action" href="/">{t.home}</Link>
      </div>
    </section>
  );
}
