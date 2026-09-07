import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex min-h-40 w-full min-w-0 resize-y rounded-lg border border-border bg-background px-3 py-3 text-base leading-7 transition-colors placeholder:text-muted-foreground focus-visible:border-ring disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-red-600 dark:aria-invalid:border-red-400 sm:text-sm",
        className,
      )}
      {...props}
    />
  );
}
