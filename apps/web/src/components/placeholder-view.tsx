"use client";

import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";

export type PlaceholderViewName = "home" | "automations" | "knowledge" | "settings";

const placeholderContent = {
  home: ["homeTitle", "homeDescription", ["homeFeatureOne", "homeFeatureTwo", "homeFeatureThree"]],
  automations: ["automationsTitle", "automationsDescription", ["automationsFeatureOne", "automationsFeatureTwo", "automationsFeatureThree"]],
  knowledge: ["knowledgeTitle", "knowledgeDescription", ["knowledgeFeatureOne", "knowledgeFeatureTwo", "knowledgeFeatureThree"]],
  settings: ["settingsTitle", "settingsDescription", ["settingsFeatureOne", "settingsFeatureTwo", "settingsFeatureThree"]],
} as const;

export function PlaceholderView({ view }: { view: PlaceholderViewName }) {
  const { t } = useWorkspace();
  const [titleKey, descriptionKey, featureKeys] = placeholderContent[view];
  const Icon = view === "home" ? Icons.home : view === "automations" ? Icons.spark : view === "knowledge" ? Icons.book : Icons.settings;

  return (
    <section className="placeholder-stage">
      <div className="placeholder-card">
        <div className="placeholder-icon"><Icon /></div>
        <p className="eyebrow">{t.plannedArea}</p>
        <h1>{t[titleKey]}</h1>
        <p className="placeholder-copy">{t[descriptionKey]}</p>
        <div className="feature-list">
          {featureKeys.map((key) => <div key={key}><span className="status-dot" />{t[key]}</div>)}
        </div>
        <Link className="placeholder-action" href="/"><Icons.chat />{t.backToChat}</Link>
      </div>
    </section>
  );
}
