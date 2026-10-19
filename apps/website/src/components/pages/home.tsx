import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  CalendarDays,
  Cable,
  Cloud,
  CloudOff,
  House,
  Lightbulb,
  LockKeyhole,
  Music2,
  ScanLine,
  Server,
  ShieldCheck,
  Users,
} from "lucide-react";
import {
  github,
  href,
  statusOf,
  type Dictionary,
  type Locale,
} from "@/lib/site";
import { Logo } from "../logo";
import { Ecosystem } from "../ecosystem";
import { VeloraVoicePreview } from "../velora-voice-preview";
import { HowKyrionWorks } from "../how-kyrion-works";
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
          <p className="mt-10 max-w-2xl border-l-2 border-accent/40 pl-4 text-xs leading-6 text-muted-foreground">
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
      <section className="border-b border-border py-20 sm:py-24">
        <Container>
          <div className="grid overflow-hidden rounded-2xl border border-border lg:grid-cols-[0.8fr_1.2fr]">
            <div className="relative flex min-h-64 items-center justify-center overflow-hidden border-b border-border bg-muted/30 p-6 lg:border-r lg:border-b-0">
              <div
                aria-hidden="true"
                className="core-halo pointer-events-none absolute inset-0"
              />
              <VeloraVoicePreview
                locale={locale}
                label={t.home.veloraPlay}
                speakingLabel={t.home.veloraSpeaking}
                voiceNote={t.home.veloraVoiceNote}
                unavailableLabel={t.home.veloraUnavailable}
                welcomedLabel={t.home.veloraWelcomed}
              />
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
      <section className="py-20 sm:py-28">
        <Container className="grid items-start gap-12 xl:grid-cols-[0.85fr_1.15fr] xl:gap-16">
          <SectionHeader
            eyebrow={t.home.connectionEyebrow}
            title={t.home.connectionTitle}
            description={t.home.connectionDescription}
          />
          <div className="grid gap-4 sm:grid-cols-3">
            {t.home.connectionCards.map((card, i) => (
              <FeatureCard
                key={card.title}
                title={card.title}
                description={card.description}
                icon={[House, Music2, CalendarDays][i]}
              />
            ))}
          </div>
        </Container>
      </section>
      <HowKyrionWorks t={t.home} />
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
      <section className="border-y border-border bg-muted/35 py-20 sm:py-28">
        <Container>
          <SectionHeader
            eyebrow={t.home.localCloudEyebrow}
            title={t.home.localCloudTitle}
            description={t.home.localCloudDescription}
          />
          <div className="mt-12 grid gap-4 lg:grid-cols-2">
            <FeatureCard
              title={t.home.localCard.title}
              description={t.home.localCard.description}
              icon={CloudOff}
            >
              <span className="font-mono text-[11px] tracking-[0.12em] text-accent">
                {t.home.localCard.label}
              </span>
            </FeatureCard>
            <FeatureCard
              title={t.home.cloudCard.title}
              description={t.home.cloudCard.description}
              icon={Cloud}
            >
              <span className="font-mono text-[11px] tracking-[0.12em] text-accent">
                {t.home.cloudCard.label}
              </span>
            </FeatureCard>
          </div>
        </Container>
      </section>
      <section className="py-20 sm:py-28">
        <Container className="grid items-center gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-20">
          <div>
            <SectionHeader
              eyebrow={t.home.permissionsEyebrow}
              title={t.home.permissionsTitle}
              description={t.home.permissionsDescription}
            />
            <div className="mt-8 flex flex-wrap gap-3 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-2">
                <ShieldCheck
                  className="size-4 text-accent"
                  aria-hidden="true"
                />
                {t.home.permissionsNote}
              </span>
            </div>
          </div>
          <aside
            className="rounded-2xl border border-border bg-card p-6 sm:p-8"
            aria-labelledby="permission-model-title"
          >
            <h3
              id="permission-model-title"
              className="text-xl font-medium tracking-tight"
            >
              {t.home.permissionModel.title}
            </h3>
            <dl className="mt-5 divide-y divide-border">
              {t.home.permissionModel.items.map((item) => (
                <div key={item.title} className="py-5">
                  <dt className="flex flex-wrap items-center justify-between gap-3 text-sm font-medium">
                    {item.title}
                    <StatusBadge
                      status={statusOf(item.status)}
                      labels={t.status}
                    />
                  </dt>
                  <dd className="mt-3 text-sm leading-7 text-muted-foreground">
                    {item.description}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="border-t border-border pt-5 text-xs leading-6 text-muted-foreground">
              {t.home.permissionModel.note}
            </p>
          </aside>
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
          <SectionHeader
            eyebrow={t.home.integrationsEyebrow}
            title={t.home.integrationsTitle}
            description={t.home.integrationsDescription}
          />
          <div className="mt-12 grid gap-4 lg:grid-cols-3">
            {t.home.integrations.map((group, i) => (
              <article
                key={group.title}
                className="rounded-xl border border-border bg-card p-7 sm:p-8"
              >
                <div className="mb-7 flex items-center gap-3">
                  {[Cable, Lightbulb, Cloud][i] &&
                    (() => {
                      const Icon = [Cable, Lightbulb, Cloud][i];
                      return (
                        <Icon
                          className="size-6 text-muted-foreground"
                          strokeWidth={1.4}
                          aria-hidden="true"
                        />
                      );
                    })()}
                  <h3 className="text-xl font-medium tracking-tight">
                    {group.title}
                  </h3>
                </div>
                <div className="space-y-3">
                  {group.items.map((item) => (
                    <div
                      key={item.name}
                      className="flex flex-wrap items-center justify-between gap-3 text-sm"
                    >
                      <span>{item.name}</span>
                      <StatusBadge
                        status={statusOf(item.status)}
                        labels={t.status}
                      />
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
          <p className="mt-6 max-w-3xl text-sm leading-7 text-muted-foreground">
            {t.home.integrationNote}
          </p>
        </Container>
      </section>
      <section className="border-t border-border bg-muted/35 py-20 sm:py-28">
        <Container className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:gap-20">
          <SectionHeader
            eyebrow={t.home.hardwareEyebrow}
            title={t.home.hardwareTitle}
            description={t.home.hardwareDescription}
          />
          <div className="space-y-3">
            {t.home.hardwareFaq.map((item) => (
              <details
                key={item.question}
                className="group rounded-xl border border-border bg-card p-6"
              >
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
                  {item.question}
                  <span className="text-xl text-muted-foreground transition-transform group-open:rotate-45">
                    +
                  </span>
                </summary>
                <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">
                  {item.answer}
                </p>
              </details>
            ))}
            <a
              href={`${github}/blob/HEAD/docs/development-startup.md`}
              className="inline-flex min-h-11 items-center gap-2 rounded-md text-sm font-medium text-accent"
            >
              {t.docs.cards[0].title}
              <ArrowUpRight aria-hidden="true" className="size-4" />
            </a>
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
