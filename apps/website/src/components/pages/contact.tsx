import { MessageSquare, FlaskConical } from "lucide-react";
import type { Dictionary, Locale } from "@/lib/site";
import { ContactForm } from "../contact-form";
import { Container, DevelopmentBanner, PageHero } from "../site-ui";

export function ContactPage({ t, locale }: { t: Dictionary; locale: Locale }) {
  return (
    <>
      <PageHero {...t.contact} />
      <Container className="grid items-start gap-10 py-14 lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-14">
        <ContactForm t={t.contact} />
        <aside className="space-y-8 lg:sticky lg:top-28">
          <div className="rounded-xl border border-border bg-muted/35 p-6">
            <MessageSquare
              aria-hidden="true"
              className="mb-6 size-7 text-accent"
              strokeWidth={1.5}
            />
            <h2 className="text-xl font-medium tracking-tight">
              {t.contact.asideTitle}
            </h2>
            <p className="mt-4 text-sm leading-7 text-muted-foreground">
              {t.contact.asideDescription}
            </p>
            <div className="mt-6">
              <DevelopmentBanner t={t} locale={locale} />
            </div>
          </div>
          <div className="px-2">
            <FlaskConical
              aria-hidden="true"
              className="mb-4 size-6 text-muted-foreground"
              strokeWidth={1.5}
            />
            <h2 className="font-medium">{t.contact.testingAsideTitle}</h2>
            <p className="mt-3 text-sm leading-7 text-muted-foreground">
              {t.contact.testingNote}
            </p>
          </div>
        </aside>
      </Container>
    </>
  );
}
