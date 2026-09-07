import { LockKeyhole, Server, Target } from "lucide-react";
import type { Dictionary, Locale } from "@/lib/site";
import { Ecosystem } from "../ecosystem";
import {
  Container,
  CTASection,
  FeatureCard,
  PageHero,
  SectionHeader,
} from "../site-ui";

export function AboutPage({ t, locale }: { t: Dictionary; locale: Locale }) {
  const icons = [Server, LockKeyhole, Target];
  return (
    <>
      <PageHero {...t.about} />
      <section className="py-20 sm:py-28">
        <Container className="grid items-center gap-12 lg:grid-cols-2 lg:gap-20">
          <div>
            <SectionHeader
              title={t.about.introTitle}
              description={t.about.intro}
            />
            <p className="mt-6 text-base leading-8 text-muted-foreground">
              {t.about.paragraph}
            </p>
          </div>
          <Ecosystem t={t.home} />
        </Container>
      </section>
      <section className="border-y border-border bg-muted/35 py-16">
        <Container className="grid gap-4 md:grid-cols-3">
          {t.about.principles.map((principle, i) => (
            <FeatureCard key={principle.title} {...principle} icon={icons[i]} />
          ))}
        </Container>
      </section>
      <section className="py-20 sm:py-28">
        <Container className="grid gap-8 lg:grid-cols-2">
          <SectionHeader title={t.about.visionTitle} />
          <div className="space-y-6 text-lg leading-8 text-muted-foreground">
            <p>{t.about.vision}</p>
            <p>{t.about.origin}</p>
          </div>
        </Container>
      </section>
      <CTASection t={t} locale={locale} />
    </>
  );
}
