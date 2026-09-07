"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import {
  github,
  href,
  type Dictionary,
  type Locale,
  type Page,
} from "@/lib/site";
import { Logo } from "./logo";
import { LanguageFlag } from "./language-flag";
import { ThemeToggle } from "./theme-toggle";
import { Button } from "./ui/button";

export function SiteHeader({
  locale,
  page,
  t,
}: {
  locale: Locale;
  page: Page;
  t: Dictionary["nav"];
}) {
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const close = () => setOpen(false);
    media.addEventListener("change", close);
    return () => media.removeEventListener("change", close);
  }, []);
  const links = (
    ["product", "about", "development", "docs", "contact"] as const
  ).map((item) => (
    <Link
      key={item}
      href={href(locale, item)}
      aria-current={page === item ? "page" : undefined}
      onClick={() => setOpen(false)}
      className="flex min-h-11 items-center rounded-md px-3 text-sm text-muted-foreground transition-colors hover:text-foreground aria-[current=page]:text-foreground"
    >
      {t[item]}
    </Link>
  ));
  return (
    <header
      className="sticky top-0 z-50 border-b border-border bg-background/95"
      onKeyDown={(event) => {
        if (open && event.key === "Escape") {
          setOpen(false);
          toggle.current?.focus();
        }
      }}
    >
      <a
        href="#main"
        className="fixed top-3 left-3 z-50 -translate-y-24 rounded-lg bg-primary px-5 py-3 text-primary-foreground focus:translate-y-0"
      >
        {t.skip}
      </a>
      <div className="mx-auto flex min-h-20 max-w-7xl items-center justify-between gap-3 px-5 sm:px-8">
        <Link href={href(locale)} aria-label={t.home}>
          <Logo
            priority
            className="w-[112px] min-[380px]:w-[132px] sm:w-[156px]"
          />
        </Link>
        <nav aria-label={t.label} className="hidden items-center lg:flex">
          {links}
          <a
            href={github}
            className="flex min-h-11 items-center gap-1 px-3 text-sm text-muted-foreground hover:text-foreground"
          >
            {t.github}
            <ArrowUpRight className="size-3" aria-hidden="true" />
          </a>
        </nav>
        <div className="flex items-center gap-2">
          <Link
            href={href(locale === "en" ? "de" : "en", page)}
            hrefLang={locale === "en" ? "de" : "en"}
            aria-label={t.language}
            title={t.language}
            className="flex min-h-11 items-center gap-2 rounded-md px-2 text-xs text-muted-foreground hover:text-foreground"
          >
            <LanguageFlag locale={locale === "en" ? "de" : "en"} />
            {locale === "en" ? "DE" : "EN"}
          </Link>
          <ThemeToggle labels={t} />
          <Button
            ref={toggle}
            variant="ghost"
            className="px-3 lg:hidden"
            aria-expanded={open}
            aria-controls="mobile-navigation"
            aria-label={open ? t.close : t.menu}
            onClick={() => setOpen(!open)}
          >
            <span aria-hidden="true">{open ? <X /> : <Menu />}</span>
          </Button>
        </div>
      </div>
      <div
        ref={panel}
        id="mobile-navigation"
        hidden={!open}
        className="max-h-[calc(100dvh-5rem)] overflow-y-auto border-t border-border px-5 py-4 lg:hidden"
        onBlur={(event) => {
          if (
            !panel.current?.contains(event.relatedTarget) &&
            event.relatedTarget !== toggle.current
          )
            setOpen(false);
        }}
      >
        <nav aria-label={t.label} className="flex flex-col">
          {links}
          <a
            href={github}
            className="flex min-h-11 items-center gap-2 px-3 text-sm"
          >
            {t.github}
            <ArrowUpRight aria-hidden="true" className="size-4" />
          </a>
          <Link
            href={href(locale === "en" ? "de" : "en", page)}
            hrefLang={locale === "en" ? "de" : "en"}
            onClick={() => setOpen(false)}
            className="flex min-h-11 items-center gap-2 px-3 text-sm"
          >
            <LanguageFlag locale={locale === "en" ? "de" : "en"} />
            {t.language}
          </Link>
        </nav>
      </div>
    </header>
  );
}
