import type { Dictionary, Page } from "@/lib/site";
import { Container } from "../site-ui";

export function LegalPage({ t, page }: { t: Dictionary; page: Page }) {
  const legal = t.legal[page as "privacy" | "terms"];
  return (
    <section className="border-b border-border py-16 sm:py-24">
      <Container>
        <article className="max-w-3xl">
          <p className="mb-6 font-mono text-xs tracking-[0.16em] text-accent">
            {legal.eyebrow}
          </p>
          <h1 className="text-4xl font-medium tracking-[-0.05em] sm:text-6xl">
            {legal.title}
          </h1>
          <p className="mt-7 max-w-2xl text-lg leading-8 text-muted-foreground">
            {legal.intro}
          </p>
          <div className="mt-14 divide-y divide-border">
            {legal.sections.map((section) => (
              <section className="py-8 first:pt-0" key={section.title}>
                <h2 className="text-xl font-medium tracking-tight">
                  {section.title}
                </h2>
                <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
                  {section.body}
                  {"google" in section && section.google && (
                    <>
                      {" "}
                      <a
                        className="underline underline-offset-4 hover:text-foreground"
                        href="https://developers.google.com/terms/api-services-user-data-policy"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Google API Services User Data Policy
                      </a>
                      .
                    </>
                  )}
                </p>
              </section>
            ))}
          </div>
        </article>
      </Container>
    </section>
  );
}
