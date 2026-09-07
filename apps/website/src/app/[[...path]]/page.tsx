import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  dictionaries,
  href,
  pages,
  resolveRoute,
  siteUrl,
  type Locale,
} from "@/lib/site";
import { HomePage } from "@/components/pages/home";
import { ProductPage } from "@/components/pages/product";
import { AboutPage } from "@/components/pages/about";
import { DevelopmentPage } from "@/components/pages/development";
import { DocsPage } from "@/components/pages/docs";

type Props = { params: Promise<{ path?: string[] }> };

export function generateStaticParams() {
  return (["en", "de"] as Locale[]).flatMap((locale) =>
    pages.map((page) => ({
      path: href(locale, page).split("/").filter(Boolean),
    })),
  );
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const route = resolveRoute((await params).path);
  if (!route) return {};
  const { locale, page } = route;
  const t = dictionaries[locale];
  const title = page === "home" ? t.meta.title : `${t.nav[page]} — Kyrion`;
  const description =
    page === "home" ? t.meta.description : t[page].description;
  const url = new URL(href(locale, page), siteUrl).href;
  return {
    title,
    description,
    alternates: {
      canonical: url,
      languages: {
        en: href("en", page),
        de: href("de", page),
        "x-default": href("en", page),
      },
    },
    openGraph: {
      title,
      description,
      url,
      siteName: "Kyrion",
      type: "website",
      locale: locale === "de" ? "de_CH" : "en_GB",
      alternateLocale: locale === "de" ? "en_GB" : "de_CH",
      images: [
        {
          url: "/branding/og-image.png",
          width: 1200,
          height: 630,
          alt: "Kyrion",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: ["/branding/og-image.png"],
    },
  };
}

const components = {
  home: HomePage,
  product: ProductPage,
  about: AboutPage,
  development: DevelopmentPage,
  docs: DocsPage,
};

export default async function PublicPage({ params }: Props) {
  const route = resolveRoute((await params).path);
  if (!route) notFound();
  const Component = components[route.page];
  return <Component t={dictionaries[route.locale]} locale={route.locale} />;
}
