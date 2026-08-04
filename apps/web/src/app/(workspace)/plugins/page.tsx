"use client";

import Link from "next/link";
import { Icons } from "@/components/icons";
import { useWorkspace } from "@/components/app-shell";

export default function PluginsPage() {
  const { t } = useWorkspace();
  return <section className="plugins-stage">
    <header className="plugins-header"><div><p className="eyebrow">Kyrion Extensions</p><h1>{t.pluginsTitle}</h1><p>{t.pluginsDescription}</p></div></header>
    <div className="plugin-grid"><article className="plugin-card">
      <div className="plugin-mark"><Icons.plugins /></div>
      <div className="plugin-badges"><span>{t.pluginOfficial}</span><span>{t.pluginAvailable}</span></div>
      <h2>Nanoleaf</h2><p>{t.pluginNanoleafDescription}</p>
      <Link href="/plugins/nanoleaf">{t.pluginOpen}</Link>
    </article></div>
  </section>;
}
