"use client";

import { useSyncExternalStore } from "react";
import { useTheme } from "next-themes";
import { Monitor, Moon, Sun } from "lucide-react";
import type { Dictionary } from "@/lib/site";

const subscribe = () => () => {};

export function ThemeToggle({ labels }: { labels: Dictionary["nav"] }) {
  const mounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  const { theme, setTheme } = useTheme();
  const selected = mounted ? theme : "system";
  const Icon =
    selected === "dark" ? Moon : selected === "light" ? Sun : Monitor;
  return (
    <div className="relative flex items-center">
      <Icon
        aria-hidden="true"
        className="pointer-events-none absolute left-3 size-4 text-muted-foreground"
      />
      <select
        aria-label={labels.theme}
        value={selected ?? "system"}
        onChange={(event) => setTheme(event.target.value)}
        className="min-h-11 max-w-32 rounded-lg border border-border bg-background py-2 pr-2 pl-9 text-xs"
      >
        <option value="system">{labels.system}</option>
        <option value="light">{labels.light}</option>
        <option value="dark">{labels.dark}</option>
      </select>
    </div>
  );
}
