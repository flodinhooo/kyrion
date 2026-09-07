import { ArrowUpRight } from "lucide-react";
import {
  github,
  statusOf,
  type Dictionary,
  type Locale,
  type Status,
} from "@/lib/site";
import {
  Container,
  CTASection,
  PageHero,
  SectionHeader,
  StatusBadge,
} from "../site-ui";

export function DevelopmentPage({
  t,
  locale,
}: {
  t: Dictionary;
  locale: Locale;
}) {
  const statuses: Status[] = [
    "available",
    "experimental",
    "development",
    "planned",
  ];
  return (
    <>
      <PageHero {...t.development}>
        <StatusBadge status="development" labels={t.status} />
      </PageHero>
      <section className="py-20">
        <Container>
          <div className="relative overflow-hidden rounded-2xl border border-border bg-muted/40 p-7 sm:p-12">
            <div
              aria-hidden="true"
              className="core-line absolute inset-x-0 top-0 h-px"
            />
            <SectionHeader
              eyebrow={t.development.checkpoint}
              title={t.development.checkpointTitle}
              description={t.development.checkpointDescription}
            />
            <a
              href={`${github}/tree/HEAD/docs/status`}
              className="mt-7 inline-flex min-h-11 items-center gap-2 text-sm font-medium"
            >
              {t.development.source}
              <ArrowUpRight aria-hidden="true" className="size-4" />
            </a>
          </div>
        </Container>
      </section>
      <section className="pb-20">
        <Container>
          <SectionHeader title={t.development.areasTitle} />
          <div className="mt-10 divide-y divide-border border-y border-border">
            {t.capabilities.map((item) => (
              <article
                key={item.title}
                className="grid items-start gap-4 py-7 md:grid-cols-[200px_1fr_160px]"
              >
                <h3 className="text-base font-medium">{item.title}</h3>
                <p className="max-w-2xl text-sm leading-7 text-muted-foreground">
                  {item.description}
                </p>
                <StatusBadge status={statusOf(item.status)} labels={t.status} />
              </article>
            ))}
          </div>
        </Container>
      </section>
      <section className="border-y border-border bg-muted/35 py-16">
        <Container>
          <h2 className="text-2xl font-medium tracking-tight">
            {t.development.legendTitle}
          </h2>
          <div className="mt-7 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {statuses.map((status, i) => (
              <div key={status}>
                <StatusBadge status={status} labels={t.status} />
                <p className="mt-4 text-sm leading-7 text-muted-foreground">
                  {t.development.legend[i]}
                </p>
              </div>
            ))}
          </div>
        </Container>
      </section>
      <section className="py-20 sm:py-28">
        <Container>
          <SectionHeader
            title={t.development.roadmapTitle}
            description={t.development.roadmapDescription}
          />
          <ol className="mt-12 grid gap-6 md:grid-cols-3">
            {t.development.roadmap.map((item, i) => (
              <li key={item.title} className="border-t border-border pt-6">
                <div className="mb-6 flex items-center justify-between gap-3">
                  <span className="font-mono text-sm text-muted-foreground">
                    0{i + 1}
                  </span>
                  <StatusBadge
                    status={statusOf(item.status)}
                    labels={t.status}
                  />
                </div>
                <h3 className="text-xl font-medium tracking-tight">
                  {item.title}
                </h3>
                <p className="mt-4 text-sm leading-7 text-muted-foreground">
                  {item.description}
                </p>
              </li>
            ))}
          </ol>
          <p className="mt-12 max-w-3xl border-l-2 border-accent/40 pl-5 text-sm leading-7 text-muted-foreground">
            {t.development.disclaimer}
          </p>
        </Container>
      </section>
      <CTASection t={t} locale={locale} />
    </>
  );
}
