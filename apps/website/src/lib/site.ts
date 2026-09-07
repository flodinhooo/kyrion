import en from "@/locales/en.json";
import de from "@/locales/de.json";

export type Locale = "en" | "de";
export type Dictionary = typeof en;
export type Status = keyof Dictionary["status"];
export const pages = [
  "home",
  "product",
  "about",
  "development",
  "docs",
  "contact",
] as const;
export type Page = (typeof pages)[number];
export const dictionaries: Record<Locale, Dictionary> = { en, de };
export const github = "https://github.com/flodinhooo/kyrion";
export const siteUrl = "https://kyrion.ch";

export function href(locale: Locale, page: Page = "home") {
  return (
    `${locale === "de" ? "/de" : ""}${page === "home" ? "" : `/${page}`}` || "/"
  );
}

export function resolveRoute(
  path: string[] = [],
): { locale: Locale; page: Page } | null {
  const locale = path[0] === "de" ? "de" : "en";
  const parts = locale === "de" ? path.slice(1) : path;
  const page = parts[0] ?? "home";
  if (parts.length > 1 || (parts.length === 1 && page === "home")) return null;
  const knownPage = pages.find((candidate) => candidate === page);
  return knownPage ? { locale, page: knownPage } : null;
}

export function statusOf(value: string): Status {
  if (
    value === "available" ||
    value === "experimental" ||
    value === "development" ||
    value === "planned"
  )
    return value;
  throw new Error(`Unknown content status: ${value}`);
}
