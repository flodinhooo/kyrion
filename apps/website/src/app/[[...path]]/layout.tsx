import type { Metadata } from "next";
import type { ReactNode } from "react";
import { dictionaries, resolveRoute, siteUrl } from "@/lib/site";
import { ThemeProvider } from "@/components/theme-provider";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import "../globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  robots: { index: true, follow: true },
  icons: {
    icon: [{ url: "/branding/favicon.svg", type: "image/svg+xml" }],
    apple: "/branding/apple-touch-icon.png",
  },
};

export default async function RootLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ path?: string[] }>;
}) {
  const route = resolveRoute((await params).path) ?? {
    locale: "en",
    page: "home",
  };
  const t = dictionaries[route.locale];
  return (
    <html lang={route.locale} suppressHydrationWarning>
      <body className="antialiased">
        <ThemeProvider>
          <SiteHeader locale={route.locale} page={route.page} t={t.nav} />
          <main id="main" tabIndex={-1}>
            {children}
          </main>
          <SiteFooter locale={route.locale} t={t} />
        </ThemeProvider>
      </body>
    </html>
  );
}
