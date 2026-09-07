import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export function Input({ className, type, ...props }: ComponentProps<"input">) {
  return (
    <input
      data-slot="input"
      type={type}
      className={cn(
        "flex min-h-11 w-full min-w-0 rounded-lg border border-border bg-background px-3 py-2 text-base transition-colors placeholder:text-muted-foreground focus-visible:border-ring disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-red-600 dark:aria-invalid:border-red-400 sm:text-sm",
        className,
      )}
      {...props}
    />
  );
}
