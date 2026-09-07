import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { github, href, type Dictionary, type Locale } from "@/lib/site";
import { Logo } from "./logo";
import { Container } from "./site-ui";

export function SiteFooter({ locale, t }: { locale: Locale; t: Dictionary }) {
  return (
    <footer className="border-t border-border bg-muted/40 py-14">
      <Container>
        <div className="flex flex-col justify-between gap-10 md:flex-row">
          <div>
            <Link href={href(locale)} aria-label={t.nav.home}>
              <Logo />
            </Link>
            <p className="mt-5 text-sm">{t.common.footer}</p>
            <p className="mt-3 max-w-sm text-sm leading-6 text-muted-foreground">
              {t.common.footerNote}
            </p>
          </div>
          <nav
            aria-label={t.common.footerLinks}
            className="grid grid-cols-2 gap-x-12 gap-y-2 text-sm"
          >
            {(["product", "about", "development", "docs"] as const).map(
              (page) => (
                <Link
                  className="flex min-h-11 items-center text-muted-foreground hover:text-foreground"
                  key={page}
                  href={href(locale, page)}
                >
                  {t.nav[page]}
                </Link>
              ),
            )}
            <a
              href={github}
              className="flex min-h-11 items-center gap-2 text-muted-foreground hover:text-foreground"
            >
              {t.nav.github}
              <ArrowUpRight aria-hidden="true" className="size-3" />
            </a>
          </nav>
        </div>
        <div className="mt-12 flex flex-wrap justify-between gap-4 border-t border-border pt-6 font-mono text-xs text-muted-foreground">
          <span>{t.common.copyright}</span>
          <span>{t.common.footerPrinciple}</span>
        </div>
      </Container>
    </footer>
  );
}
