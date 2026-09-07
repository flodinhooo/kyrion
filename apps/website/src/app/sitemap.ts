import type { MetadataRoute } from "next";
import { href, pages, siteUrl, type Locale } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  return (["en", "de"] as Locale[]).flatMap((locale) =>
    pages.map((page) => ({
      url: `${siteUrl}${href(locale, page)}`,
      alternates: {
        languages: {
          en: `${siteUrl}${href("en", page)}`,
          de: `${siteUrl}${href("de", page)}`,
        },
      },
    })),
  );
}
