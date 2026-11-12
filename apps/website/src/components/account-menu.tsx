"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { UserRound } from "lucide-react";
import { dictionaries, href, type Locale } from "@/lib/site";
import { useAccountSession } from "./account-session";

export function AccountMenu({ locale }: { locale: Locale }) {
  const { status, logout, busy } = useAccountSession();
  const t = dictionaries[locale].account;
  const menu = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (event.target instanceof Node && !menu.current?.contains(event.target))
        menu.current?.removeAttribute("open");
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);
  if (!status?.session)
    return (
      <Link
        href={href(locale, "account")}
        aria-label={t.login}
        className="inline-flex min-h-11 items-center gap-2 rounded-md px-2 text-sm hover:bg-muted sm:px-3"
      >
        <UserRound aria-hidden="true" className="size-4" />
        <span className="hidden sm:inline">{t.signInShort}</span>
      </Link>
    );
  return (
    <details
      ref={menu}
      className="relative"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          menu.current?.removeAttribute("open");
          menu.current?.querySelector("summary")?.focus();
        }
      }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget))
          menu.current?.removeAttribute("open");
      }}
    >
      <summary
        className="flex min-h-11 cursor-pointer list-none items-center gap-2 rounded-md border border-border px-3 text-sm hover:bg-muted"
        aria-label={t.menu}
      >
        <UserRound aria-hidden="true" className="size-4" />
        <span className="hidden sm:inline">{t.menu}</span>
      </summary>
      <nav
        aria-label={t.menu}
        className="fixed top-20 right-5 left-5 z-50 mt-2 rounded-xl border border-border bg-background p-2 shadow-xl sm:absolute sm:top-full sm:right-0 sm:left-auto sm:w-56"
      >
        <Link
          href={href(locale, "account")}
          onClick={(event) => {
            menu.current?.removeAttribute("open");
            if (
              !event.ctrlKey &&
              !event.metaKey &&
              !event.shiftKey &&
              !event.altKey &&
              window.location.pathname === href(locale, "account")
            ) {
              event.preventDefault();
              window.location.hash = "overview";
            }
          }}
          className="flex min-h-11 items-center rounded-lg px-3 text-sm hover:bg-muted"
        >
          {t.overview}
        </Link>
        <Link
          href={href(locale, "connect")}
          onClick={() => menu.current?.removeAttribute("open")}
          className="flex min-h-11 items-center rounded-lg px-3 text-sm hover:bg-muted"
        >
          {t.linkTab}
        </Link>
        <form action="/api/account/manage" method="get">
          <button
            type="submit"
            className="flex min-h-11 items-center rounded-lg px-3 text-sm hover:bg-muted"
          >
            {t.manage}
          </button>
        </form>
        <button
          type="button"
          disabled={busy}
          onClick={() => void logout()}
          className="flex min-h-11 w-full items-center rounded-lg px-3 text-sm hover:bg-muted disabled:opacity-50"
        >
          {t.logout}
        </button>
      </nav>
    </details>
  );
}
