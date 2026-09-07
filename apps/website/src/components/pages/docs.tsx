import { ArrowUpRight, BookOpen, ChevronDown, Search } from "lucide-react";
import { github, type Dictionary, type Locale } from "@/lib/site";
import { Container, PageHero, StatusBadge } from "../site-ui";
import { Button } from "../ui/button";

export function DocsPage({ t }: { t: Dictionary; locale: Locale }) {
  return (
    <>
      <PageHero {...t.docs}>
        <StatusBadge status="development" labels={t.status} />
      </PageHero>
      <Container className="grid gap-10 py-14 lg:grid-cols-[220px_1fr] lg:gap-16">
        <aside
          aria-label={t.docs.sidebar}
          className="lg:border-r lg:border-border lg:pr-7"
        >
          <div
            className="flex items-center justify-between gap-2 rounded-lg border border-border px-3 py-3 text-xs text-muted-foreground"
            aria-disabled="true"
          >
            {t.docs.version}
            <ChevronDown aria-hidden="true" className="size-3" />
          </div>
          <div
            className="mt-4 flex items-center gap-2 rounded-lg border border-border px-3 py-3 text-xs text-muted-foreground"
            aria-disabled="true"
          >
            <Search aria-hidden="true" className="size-4" />
            {t.docs.search}
          </div>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            {t.docs.searchNote}
          </p>
          <ul className="mt-8 flex flex-wrap gap-2 lg:flex-col">
            {t.docs.sections.map((label, i) => (
              <li
                key={label}
                className={
                  i === 0
                    ? "rounded-md bg-muted px-3 py-3 text-sm font-medium"
                    : "px-3 py-3 text-sm text-muted-foreground"
                }
              >
                {label}
              </li>
            ))}
          </ul>
        </aside>
        <article className="min-w-0 pb-10">
          <BookOpen
            aria-hidden="true"
            className="mb-6 size-8 text-accent"
            strokeWidth={1.4}
          />
          <h2 className="text-3xl font-medium tracking-tight sm:text-4xl">
            {t.docs.articleTitle}
          </h2>
          <p className="mt-5 max-w-2xl text-base leading-8 text-muted-foreground">
            {t.docs.articleDescription}
          </p>
          <Button asChild variant="outline" className="mt-6">
            <a href={`${github}/tree/HEAD/docs`}>
              {t.docs.repoLink}
              <ArrowUpRight aria-hidden="true" />
            </a>
          </Button>
          <div className="mt-12 grid gap-4 sm:grid-cols-3">
            {t.docs.cards.map((item) => (
              <section
                key={item.title}
                className="rounded-lg border border-border p-5"
              >
                <StatusBadge status="planned" labels={t.status} />
                <h3 className="mt-5 font-medium">{item.title}</h3>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  {item.description}
                </p>
              </section>
            ))}
          </div>
          <div className="mt-10 overflow-hidden rounded-xl border border-border bg-muted/40">
            <p className="border-b border-border px-5 py-3 font-mono text-xs text-muted-foreground">
              {t.docs.codeTitle}
            </p>
            <pre className="overflow-x-auto p-5 text-xs leading-7 sm:text-sm">
              <code>{t.docs.code}</code>
            </pre>
          </div>
          <p className="mt-6 text-sm leading-7 text-muted-foreground">
            {t.docs.note}
          </p>
        </article>
      </Container>
    </>
  );
}
