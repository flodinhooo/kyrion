"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AuthForm } from "@/components/auth-form";
import { BrandAsset } from "@/components/brand-asset";
import { messages, type Locale } from "@/lib/messages";
import { readPreference, writePreference } from "@/lib/browser-preferences";

export function LoginScreen({ setupRequired, registration = false }: { setupRequired: boolean | null; registration?: boolean }) {
  const [locale, setLocale] = useState<Locale>("de");
  const [pending, startTransition] = useTransition();
  const router = useRouter();
  const t = messages[locale];
  useEffect(() => {
    const saved = readPreference("kyrion-locale");
    const next = saved === "de" || saved === "en" ? saved : navigator.language.startsWith("de") ? "de" : "en";
    document.documentElement.lang = next;
    const theme = readPreference("kyrion-theme");
    if (theme === "dark" || theme === "light") document.documentElement.dataset.theme = theme;
    queueMicrotask(() => setLocale(next));
  }, []);
  return <main className="auth-stage">
    <section className="auth-card">
      <div className="auth-heading">
        <BrandAsset variant="mark" priority />
        <button className="language-button" type="button" aria-label={t.language} onClick={() => {
          const next = locale === "de" ? "en" : "de";
          setLocale(next); document.documentElement.lang = next; writePreference("kyrion-locale", next);
        }}>{locale.toUpperCase()}</button>
      </div>
      <p className="eyebrow">{setupRequired ? t.authSetupEyebrow : registration ? t.authJoinEyebrow : t.authWelcome}</p>
      <h1>{registration ? t.authSignupTitle : setupRequired ? t.authSetupTitle : t.authLoginTitle}</h1>
      <p role={setupRequired === null ? "alert" : undefined}>{setupRequired === null ? t.authCoreUnavailable : registration && !setupRequired ? t.authRegistrationDescription : setupRequired ? t.authSetupDescription : t.authLoginDescription}</p>
      {setupRequired === null
        ? <button className="auth-retry" type="button" disabled={pending} onClick={() => startTransition(() => router.refresh())}>{pending ? t.authPending : t.authRetry}</button>
        : <AuthForm setup={setupRequired} registration={registration} locale={locale} />}
      {registration && <p className="auth-footer"><Link href="/login">{t.authBackToLogin}</Link></p>}
      {!registration && setupRequired === false && <p className="auth-footer"><Link href="/signup">{t.authSignupTitle}</Link></p>}
    </section>
  </main>;
}
