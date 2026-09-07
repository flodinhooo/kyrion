import {
  AudioLines,
  Cable,
  House,
  ScanLine,
  Server,
  Sparkles,
  Users,
  Workflow,
} from "lucide-react";
import { type Dictionary, type Locale, statusOf } from "@/lib/site";
import {
  Container,
  CTASection,
  DevelopmentBanner,
  FeatureCard,
  PageHero,
  SectionHeader,
  StatusBadge,
} from "../site-ui";

export function ProductPage({ t, locale }: { t: Dictionary; locale: Locale }) {
  const icons = [
    House,
    Cable,
    Sparkles,
    Users,
    ScanLine,
    Server,
    AudioLines,
    Workflow,
    Cable,
  ];
  return (
    <>
      <PageHero {...t.product}>
        <DevelopmentBanner t={t} locale={locale} />
      </PageHero>
      <section className="py-20">
        <Container>
          <SectionHeader
            title={t.product.availableTitle}
            description={t.product.availableNote}
          />
          <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {t.capabilities.slice(0, 6).map((item, i) => (
              <FeatureCard
                key={item.title}
                title={item.title}
                description={item.description}
                icon={icons[i]}
              >
                <StatusBadge status={statusOf(item.status)} labels={t.status} />
              </FeatureCard>
            ))}
          </div>
        </Container>
      </section>
      <section className="border-t border-border bg-muted/35 py-20">
        <Container>
          <SectionHeader
            title={t.product.futureTitle}
            description={t.product.futureNote}
          />
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {t.capabilities.slice(6).map((item, i) => (
              <FeatureCard
                key={item.title}
                title={item.title}
                description={item.description}
                icon={icons[i + 6]}
              >
                <StatusBadge status={statusOf(item.status)} labels={t.status} />
              </FeatureCard>
            ))}
          </div>
        </Container>
      </section>
      <CTASection t={t} locale={locale} />
    </>
  );
}
