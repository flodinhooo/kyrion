import {
  AudioLines,
  Cpu,
  Globe,
  Lightbulb,
  Radio,
  Workflow,
  Zap,
} from "lucide-react";
import type { Dictionary } from "@/lib/site";
import { Logo } from "./logo";

export function Ecosystem({ t }: { t: Dictionary["home"] }) {
  const deviceIcons = [Lightbulb, Radio, Zap];
  const interfaceIcons = [Globe, AudioLines, Workflow, Cpu];
  return (
    <figure
      className="relative isolate overflow-hidden rounded-2xl border border-border bg-card p-5 sm:p-9"
      aria-label={t.diagramLabel}
    >
      <div
        aria-hidden="true"
        className="core-grid pointer-events-none absolute inset-0 -z-10 opacity-60"
      />
      <p className="text-center font-mono text-[10px] tracking-[0.16em] text-muted-foreground">
        {t.diagramTop}
      </p>
      <div className="mx-auto mt-5 grid max-w-sm grid-cols-3 gap-2">
        {t.diagramDevices.map((name, i) => {
          const Icon = deviceIcons[i];
          return (
            <div
              key={name}
              className="flex flex-col items-center gap-2 rounded-lg border border-border bg-background px-2 py-4 text-xs"
            >
              <Icon
                aria-hidden="true"
                className="size-4 text-muted-foreground"
                strokeWidth={1.5}
              />
              {name}
            </div>
          );
        })}
      </div>
      <div
        aria-hidden="true"
        className="mx-auto h-12 w-px bg-gradient-to-b from-border to-accent/60"
      />
      <div className="relative mx-auto flex max-w-[260px] flex-col items-center rounded-xl border border-accent/30 bg-background p-5">
        <div
          aria-hidden="true"
          className="core-halo pointer-events-none absolute -inset-12 -z-10"
        />
        <Logo mark className="size-24" />
        <p className="mt-2 text-lg font-medium">Kyrion Core</p>
        <p className="mt-2 font-mono text-[9px] tracking-widest text-muted-foreground">
          {t.diagramCore}
        </p>
      </div>
      <div
        aria-hidden="true"
        className="mx-auto h-12 w-px bg-gradient-to-b from-accent/60 to-border"
      />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {t.diagramBottom.map((name, i) => {
          const Icon = interfaceIcons[i];
          return (
            <div
              key={name}
              className="flex flex-col items-center gap-2 rounded-lg border border-border bg-background px-1 py-4 text-[11px]"
            >
              <Icon
                aria-hidden="true"
                className="size-4 text-muted-foreground"
                strokeWidth={1.5}
              />
              {name}
            </div>
          );
        })}
      </div>
      <figcaption className="mx-auto mt-7 max-w-sm text-center text-xs leading-5 text-muted-foreground">
        {t.diagramCaption}
      </figcaption>
    </figure>
  );
}
