"use client";

import { useSyncExternalStore } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import type { Dictionary } from "@/lib/site";
import { Button } from "./ui/button";

const subscribe = () => () => {};

export function ThemeToggle({ labels }: { labels: Dictionary["nav"] }) {
  const mounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  const { resolvedTheme, setTheme } = useTheme();
  const nextTheme = resolvedTheme === "dark" ? "light" : "dark";
  const label = mounted
    ? nextTheme === "light"
      ? labels.switchLight
      : labels.switchDark
    : labels.theme;
  return (
    <Button
      variant="ghost"
      className="size-11 shrink-0 p-0"
      aria-label={label}
      title={label}
      disabled={!mounted}
      onClick={() => setTheme(nextTheme)}
    >
      <Moon aria-hidden="true" className="size-5 dark:hidden" />
      <Sun aria-hidden="true" className="hidden size-5 dark:block" />
    </Button>
  );
}
