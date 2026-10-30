import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  House,
  Search,
  Sparkles,
} from "lucide-react";
import {
  github,
  href,
  statusOf,
  type Dictionary,
  type Locale,
} from "@/lib/site";
import {
  Container,
  FeatureCard,
  PageHero,
  SectionHeader,
  StatusBadge,
} from "../site-ui";
import { Button } from "../ui/button";

type Props = { t: Dictionary; locale: Locale };

function AudiencePage({
  t,
  locale,
  audience,
}: Props & { audience: "private" | "business" }) {
  const content = t[audience];
  const icons = [House, CalendarDays, Sparkles, Search];
  return (
    <>
      <PageHero {...content}>
        <StatusBadge status="development" labels={t.status} />
        <p className="mt-5 max-w-3xl border-l-2 border-warm/60 pl-5 text-sm leading-7 text-muted-foreground">
          {content.notice}
        </p>
        <Button asChild className="mt-7">
          <Link href={href(locale, "contact")}>
            {content.cta}
            <ArrowRight aria-hidden="true" />
          </Link>
        </Button>
      </PageHero>
      <section className="py-16 sm:py-20">
        <Container>
          <SectionHeader
            title={content.casesTitle}
            description={
              audience === "business" ? t.business.examplesNote : undefined
            }
          />
          <div className="mt-10 grid gap-5 md:grid-cols-2">
            {content.cases.map((item, index) => (
              <FeatureCard
                key={item.title}
                title={item.title}
                description={item.description}
                icon={icons[index]}
              >
                <StatusBadge status={statusOf(item.status)} labels={t.status} />
              </FeatureCard>
            ))}
          </div>
        </Container>
      </section>
      <section className="border-y border-border bg-muted/35 py-16 sm:py-20">
        <Container className="grid gap-8 lg:grid-cols-2">
          <SectionHeader
            title={content.controlTitle}
            description={content.controlDescription}
          />
          <p className="rounded-xl border border-border bg-card p-7 text-sm leading-7 text-muted-foreground">
            {content.cloudNote}
          </p>
        </Container>
      </section>
      <section className="py-16 sm:py-20">
        <Container className="grid gap-8 lg:grid-cols-2">
          <SectionHeader
            title={content.setupTitle}
            description={content.setupDescription}
          />
          <div className="rounded-xl border border-border p-7">
            <p className="text-sm leading-7 text-muted-foreground">
              {content.setupNote}
            </p>
            {audience === "private" ? (
              <a
                className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm text-accent"
                href={`${github}/blob/HEAD/docs/development-startup.md`}
              >
                {content.setupLink}
                <ArrowUpRight aria-hidden="true" className="size-4 shrink-0" />
              </a>
            ) : (
              <Link
                className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm text-accent"
                href={href(locale, "development")}
              >
                {content.setupLink}
                <ArrowRight aria-hidden="true" className="size-4 shrink-0" />
              </Link>
            )}
          </div>
        </Container>
      </section>
      <section className="border-t border-border py-16 sm:py-20">
        <Container className="flex flex-col items-start justify-between gap-8 md:flex-row md:items-center">
          <SectionHeader
            title={content.ctaTitle}
            description={content.ctaDescription}
          />
          <Button asChild>
            <Link href={href(locale, "contact")}>
              {content.cta}
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </Container>
      </section>
    </>
  );
}

export function PrivatePage(props: Props) {
  return <AudiencePage {...props} audience="private" />;
}

export function BusinessPage(props: Props) {
  return <AudiencePage {...props} audience="business" />;
}
