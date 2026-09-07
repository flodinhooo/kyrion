import type { Metadata } from "next";
import type { ReactNode } from "react";
import en from "@/locales/en.json";
import "./globals.css";

export const metadata: Metadata = {
  title: en.title,
  description: en.comingSoon,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
