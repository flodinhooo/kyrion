import Link from "next/link";
import { ArrowRight, ArrowUpRight, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import {
  github,
  href,
  type Dictionary,
  type Locale,
  type Status,
} from "@/lib/site";
import { Button } from "./ui/button";

export function Container({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mx-auto w-full max-w-7xl px-5 sm:px-8", className)}>
      {children}
    </div>
  );
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <div className={cn("max-w-2xl", className)}>
      {eyebrow && (
        <p className="mb-5 font-mono text-[11px] font-medium tracking-[0.16em] text-accent">
          {eyebrow}
        </p>
      )}
      <h2 className="whitespace-pre-line text-3xl leading-[1.12] font-medium tracking-[-0.045em] sm:text-5xl">
        {title}
      </h2>
      {description && (
        <p className="mt-6 text-base leading-7 text-muted-foreground sm:text-lg">
          {description}
        </p>
      )}
    </div>
  );
}

export function PageHero({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <section className="border-b border-border py-20 sm:py-28">
      <Container>
        <p className="mb-7 font-mono text-xs tracking-[0.16em] text-accent">
          {eyebrow}
        </p>
        <h1 className="max-w-4xl whitespace-pre-line text-4xl leading-[1.06] font-medium tracking-[-0.055em] sm:text-6xl lg:text-7xl">
          {title}
        </h1>
        <p className="mt-7 max-w-2xl text-lg leading-8 text-muted-foreground">
          {description}
        </p>
        {children && <div className="mt-8">{children}</div>}
      </Container>
    </section>
  );
}

const statusStyles: Record<Status, string> = {
  available:
    "border-emerald-700/20 bg-emerald-700/5 text-emerald-800 dark:text-emerald-300",
  experimental:
    "border-amber-700/20 bg-amber-700/5 text-amber-800 dark:text-amber-300",
  development:
    "border-violet-600/20 bg-violet-600/5 text-violet-800 dark:text-violet-300",
  planned: "border-border bg-muted text-muted-foreground",
};

export function StatusBadge({
  status,
  labels,
}: {
  status: Status;
  labels: Dictionary["status"];
}) {
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1.5 font-mono text-[11px]",
        statusStyles[status],
      )}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {labels[status]}
    </span>
  );
}

export function DevelopmentBanner({
  t,
  locale,
}: {
  t: Dictionary;
  locale: Locale;
}) {
  return (
    <Link
      href={href(locale, "development")}
      className="inline-flex min-h-9 items-center gap-3 rounded-full border border-border bg-background px-3.5 py-2 font-mono text-[11px] text-muted-foreground hover:border-accent"
    >
      <span className="core-line size-1.5 rounded-full" aria-hidden="true" />
      {t.common.inDevelopment}
      <ArrowRight className="size-3" aria-hidden="true" />
    </Link>
  );
}

export function FeatureCard({
  title,
  description,
  icon: Icon,
  children,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  children?: ReactNode;
}) {
  return (
    <article className="group rounded-xl border border-border bg-card p-7 transition-colors hover:border-accent/40 sm:p-8">
      <Icon
        aria-hidden="true"
        strokeWidth={1.4}
        className="mb-9 size-7 text-muted-foreground transition-colors group-hover:text-accent"
      />
      {children && <div className="mb-4">{children}</div>}
      <h3 className="text-xl font-medium tracking-tight">{title}</h3>
      <p className="mt-3 text-sm leading-7 text-muted-foreground">
        {description}
      </p>
    </article>
  );
}

export function CTASection({ t, locale }: { t: Dictionary; locale: Locale }) {
  return (
    <section className="border-t border-border py-20 sm:py-24">
      <Container className="flex flex-col items-start justify-between gap-9 md:flex-row md:items-center">
        <div>
          <p className="mb-4 font-mono text-xs text-accent">
            {t.common.inDevelopment}
          </p>
          <h2 className="text-3xl font-medium tracking-tight sm:text-4xl">
            {t.common.follow}
          </h2>
          <p className="mt-4 max-w-xl text-sm leading-7 text-muted-foreground">
            {t.home.developmentNote}
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button asChild>
            <a href={github}>
              {t.common.github}
              <ArrowUpRight aria-hidden="true" />
            </a>
          </Button>
          <Button asChild variant="outline">
            <Link href={href(locale, "development")}>
              {t.nav.development}
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </Container>
    </section>
  );
}
