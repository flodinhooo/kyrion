import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  Cable,
  House,
  LockKeyhole,
  ScanLine,
  Server,
  ShieldCheck,
  Users,
} from "lucide-react";
import { github, href, type Dictionary, type Locale } from "@/lib/site";
import { Logo } from "../logo";
import { Ecosystem } from "../ecosystem";
import { Button } from "../ui/button";
import {
  Container,
  CTASection,
  DevelopmentBanner,
  FeatureCard,
  SectionHeader,
  StatusBadge,
} from "../site-ui";

export function HomePage({ t, locale }: { t: Dictionary; locale: Locale }) {
  const icons = [Server, House, LockKeyhole, Cable, Users, ScanLine];
  return (
    <>
      <section className="relative isolate overflow-hidden border-b border-border pt-14 pb-16 sm:pt-20 sm:pb-24">
        <div
          aria-hidden="true"
          className="core-grid pointer-events-none absolute inset-0 -z-10 opacity-50"
        />
        <div
          aria-hidden="true"
          className="core-halo pointer-events-none absolute -top-36 right-0 -z-10 h-[650px] w-[650px]"
        />
        <Container>
          <DevelopmentBanner t={t} locale={locale} />
          <div className="mt-10 grid items-center gap-8 lg:grid-cols-[1fr_320px]">
            <div>
              <p className="mb-6 max-w-lg font-mono text-[10px] tracking-[0.18em] text-muted-foreground sm:text-xs">
                {t.home.eyebrow}
              </p>
              <h1 className="max-w-4xl text-[clamp(2.8rem,6.8vw,5.9rem)] leading-[1.04] font-medium tracking-[-0.065em]">
                {t.home.title}
                <br />
                <span className="text-muted-foreground">
                  {t.home.titleAccent}
                </span>
              </h1>
              <p className="mt-8 max-w-xl text-lg leading-8 text-muted-foreground">
                {t.home.description}
              </p>
              <div className="mt-9 flex flex-wrap gap-3">
                <Button asChild>
                  <Link href={href(locale, "product")}>
                    {t.common.explore}
                    <ArrowRight aria-hidden="true" />
                  </Link>
                </Button>
                <Button variant="outline" asChild>
                  <Link href={href(locale, "development")}>
                    {t.common.viewDevelopment}
                  </Link>
                </Button>
              </div>
            </div>
            <div
              className="relative mx-auto hidden aspect-square w-full max-w-80 items-center justify-center lg:flex"
              aria-hidden="true"
            >
              <div className="absolute inset-0 rounded-full border border-border/70" />
              <div className="absolute inset-7 rounded-full border border-border/70" />
              <div className="absolute inset-14 rounded-full border border-border/70" />
              <Logo mark className="relative size-60" priority />
              <span className="absolute right-5 bottom-8 rounded-md border border-border bg-background px-3 py-2 font-mono text-[10px] text-muted-foreground">
                {t.home.diagramCore}
              </span>
            </div>
          </div>
          <p className="mt-12 font-mono text-[11px] leading-5 text-muted-foreground">
            {t.home.heroNote}
          </p>
        </Container>
      </section>
      <div className="border-b border-border">
        <Container className="grid gap-4 py-6 sm:grid-cols-3">
          {t.home.principles.map((text, i) => {
            const Icon = [Server, AudioLines, ShieldCheck][i];
            return (
              <div
                key={text}
                className="flex items-center gap-3 text-sm text-muted-foreground"
              >
                <Icon aria-hidden="true" className="size-4" strokeWidth={1.5} />
                {text}
              </div>
            );
          })}
        </Container>
      </div>
      <section className="py-20 sm:py-28">
        <Container>
          <SectionHeader
            eyebrow={t.home.featuresEyebrow}
            title={t.home.featuresTitle}
            description={t.home.featuresDescription}
          />
          <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {t.features.map((feature, i) => (
              <FeatureCard key={feature.title} {...feature} icon={icons[i]} />
            ))}
          </div>
          <Link
            href={href(locale, "product")}
            className="mt-8 inline-flex min-h-11 items-center gap-2 text-sm font-medium"
          >
            {t.common.learnMore}
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        </Container>
      </section>
      <section className="border-y border-border bg-muted/35 py-20 sm:py-24">
        <Container className="grid items-center gap-12 lg:grid-cols-2 lg:gap-20">
          <div>
            <SectionHeader
              eyebrow={t.home.ecosystemEyebrow}
              title={t.home.ecosystemTitle}
              description={t.home.ecosystemDescription}
            />
            <Button asChild variant="outline" className="mt-8">
              <Link href={href(locale, "about")}>
                {t.home.ecosystemLink}
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          </div>
          <Ecosystem t={t.home} />
        </Container>
      </section>
      <section className="py-20 sm:py-28">
        <Container>
          <div className="grid overflow-hidden rounded-2xl border border-border lg:grid-cols-[0.8fr_1.2fr]">
            <div
              className="relative flex min-h-64 items-center justify-center overflow-hidden border-b border-border bg-muted/30 lg:border-r lg:border-b-0"
              aria-hidden="true"
            >
              <div className="core-halo absolute inset-0" />
              <div className="flex h-24 items-center gap-2.5">
                {[16, 26, 42, 30, 66, 88, 52, 36, 68, 42, 24, 14].map(
                  (height, i) => (
                    <span
                      key={i}
                      style={{ height }}
                      className="core-line w-1.5 rounded-full opacity-55"
                    />
                  ),
                )}
              </div>
            </div>
            <div className="p-7 sm:p-12">
              <StatusBadge status="experimental" labels={t.status} />
              <div className="mt-7">
                <SectionHeader
                  eyebrow={t.home.veloraEyebrow}
                  title={t.home.veloraTitle}
                  description={t.home.veloraDescription}
                />
              </div>
              <p className="mt-7 border-l-2 border-accent/40 pl-4 font-mono text-xs leading-6 text-accent">
                {t.home.veloraRule}
              </p>
            </div>
          </div>
        </Container>
      </section>
      <section className="border-t border-border bg-muted/35 py-20 sm:py-24">
        <Container className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:gap-20">
          <SectionHeader
            eyebrow={t.home.developmentEyebrow}
            title={t.home.developmentTitle}
            description={t.home.developmentDescription}
          />
          <div className="self-center rounded-xl border border-border bg-card p-7 sm:p-9">
            <StatusBadge status="development" labels={t.status} />
            <p className="mt-5 text-sm leading-7 text-muted-foreground">
              {t.home.developmentNote}
            </p>
            <a
              href={github}
              className="mt-6 inline-flex min-h-11 items-center gap-2 text-sm font-medium"
            >
              {t.common.follow}
              <ArrowUpRight aria-hidden="true" className="size-4" />
            </a>
          </div>
        </Container>
      </section>
      <CTASection t={t} locale={locale} />
    </>
  );
}
