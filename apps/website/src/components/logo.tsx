import Image from "next/image";
import { cn } from "@/lib/utils";

export function Logo({
  mark = false,
  className,
  priority = false,
}: {
  mark?: boolean;
  className?: string;
  priority?: boolean;
}) {
  const name = mark ? "k" : "kyrion";
  return (
    <span
      className={cn(
        "inline-block shrink-0",
        mark ? "size-24" : "w-[156px]",
        className,
      )}
    >
      {(["light", "dark"] as const).map((theme) => (
        <Image
          key={theme}
          className={`brand-${theme} h-auto w-full`}
          src={`/branding/${name}-${theme}.svg`}
          width={mark ? 1024 : 3900}
          height={mark ? 1024 : 900}
          alt="Kyrion"
          unoptimized
          priority={priority}
        />
      ))}
    </span>
  );
}
