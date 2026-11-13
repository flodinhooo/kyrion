"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { href, type Dictionary, type Locale } from "@/lib/site";
import { useAccountSession } from "./account-session";
import type { LinkedInstallation } from "@/lib/account/installations";

function readRows(value: unknown): LinkedInstallation[] {
  if (
    !value ||
    typeof value !== "object" ||
    !("installations" in value) ||
    !Array.isArray(value.installations) ||
    value.installations.length > 100
  )
    throw new Error();
  return value.installations.map((row: unknown) => {
    if (
      !row ||
      typeof row !== "object" ||
      !("id" in row) ||
      typeof row.id !== "string" ||
      !("name" in row) ||
      typeof row.name !== "string" ||
      !("localUsername" in row) ||
      typeof row.localUsername !== "string" ||
      !("spaceType" in row) ||
      (row.spaceType !== "HOME" && row.spaceType !== "BUSINESS") ||
      !("linkedAt" in row) ||
      typeof row.linkedAt !== "string" ||
      !Number.isFinite(Date.parse(row.linkedAt)) ||
      !("confirmedAt" in row) ||
      typeof row.confirmedAt !== "string" ||
      !Number.isFinite(Date.parse(row.confirmedAt))
    )
      throw new Error();
    return {
      id: row.id,
      name: row.name,
      localUsername: row.localUsername,
      spaceType: row.spaceType,
      linkedAt: row.linkedAt,
      confirmedAt: row.confirmedAt,
    };
  });
}

export function LinkedInstallations({
  t,
  locale,
}: {
  t: Dictionary;
  locale: Locale;
}) {
  const { status } = useAccountSession();
  const id = status?.session?.id;
  const [rows, setRows] = useState<LinkedInstallation[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!id) return;
    let active = true;
    let inFlight: AbortController | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let retryDelay = 5000;

    async function load() {
      if (!active || inFlight || document.visibilityState !== "visible") return;
      clearTimeout(timer);
      const controller = new AbortController();
      inFlight = controller;
      const timeout = setTimeout(() => controller.abort(), 15000);
      try {
        const response = await fetch("/api/account/installations", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error();
        const result = readRows(await response.json());
        if (active) {
          setRows(result);
          setFailed(false);
          retryDelay = 5000;
        }
      } catch {
        if (active) {
          setFailed(true);
          retryDelay = Math.min(retryDelay * 2, 60000);
        }
      } finally {
        clearTimeout(timeout);
        inFlight = null;
        if (active) timer = setTimeout(() => void load(), retryDelay);
      }
    }

    void load();
    window.addEventListener("focus", load);
    document.addEventListener("visibilitychange", load);
    return () => {
      active = false;
      clearTimeout(timer);
      inFlight?.abort();
      window.removeEventListener("focus", load);
      document.removeEventListener("visibilitychange", load);
    };
  }, [id]);
  const date = (v: string) =>
    new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(
      new Date(v),
    );
  return (
    <section
      className="rounded-2xl border border-border bg-card p-6"
      aria-label={t.account.installationsTitle}
    >
      <h2 className="text-2xl font-semibold">{t.account.installationsTitle}</h2>
      <p className="mt-3 text-muted-foreground">
        {t.account.installationsHelp}
      </p>
      {failed && (
        <p role="alert" className="mt-4">
          {t.account.installationsFailed}
        </p>
      )}
      {!rows && !failed && (
        <p role="status" className="mt-4">
          {t.account.checking}
        </p>
      )}
      {rows?.length === 0 && (
        <p className="mt-5">{t.account.installationsEmpty}</p>
      )}
      <ul className="mt-5 space-y-4">
        {rows?.map((row) => (
          <li
            key={row.id}
            className="rounded-xl border border-border bg-background p-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-lg font-semibold">{row.name}</h3>
              <span className="rounded-full bg-muted px-3 py-1 text-xs">
                {row.spaceType === "HOME"
                  ? t.account.homeInstallation
                  : t.account.businessInstallation}
              </span>
            </div>
            <dl className="mt-3 grid gap-2 text-sm">
              <div>
                <dt className="inline text-muted-foreground">
                  {t.account.localAccount}:{" "}
                </dt>
                <dd className="inline">{row.localUsername}</dd>
              </div>
              <div>
                <dt className="inline text-muted-foreground">
                  {t.account.linkedOn}:{" "}
                </dt>
                <dd className="inline">{date(row.linkedAt)}</dd>
              </div>
              <div>
                <dt className="inline text-muted-foreground">
                  {t.account.lastConfirmed}:{" "}
                </dt>
                <dd className="inline">{date(row.confirmedAt)}</dd>
              </div>
            </dl>
          </li>
        ))}
      </ul>
      <Link
        href={href(locale, "connect")}
        className="mt-5 inline-flex min-h-11 items-center rounded-lg bg-primary px-5 py-3 font-medium text-primary-foreground"
      >
        {t.account.linkTab}
      </Link>
    </section>
  );
}
