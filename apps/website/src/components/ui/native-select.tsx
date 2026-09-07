import type { ComponentProps } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export function NativeSelect({
  className,
  children,
  ...props
}: ComponentProps<"select">) {
  return (
    <div className="relative min-w-0">
      <select
        data-slot="native-select"
        className={cn(
          "min-h-11 w-full min-w-0 appearance-none rounded-lg border border-border bg-background py-2 pr-9 pl-3 text-base transition-colors focus-visible:border-ring disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-red-600 dark:aria-invalid:border-red-400 sm:text-sm",
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute top-3.5 right-3 size-4 text-muted-foreground"
      />
    </div>
  );
}
