"use client";

import { useEffect, useState } from "react";
import type { Dictionary, Locale } from "@/lib/site";
import type { CredentialMethod } from "@/lib/account/credential-inventory";
import { Button } from "@/components/ui/button";

function methods(value: unknown): CredentialMethod[] {
  if (!value || typeof value !== "object" || !("inventory" in value))
    throw Error();
  const inventory = value.inventory;
  if (
    !inventory ||
    typeof inventory !== "object" ||
    !("methods" in inventory) ||
    !Array.isArray(inventory.methods)
  )
    throw Error();
  return inventory.methods.map((m: unknown) => {
    if (
      !m ||
      typeof m !== "object" ||
      !("id" in m) ||
      typeof m.id !== "string" ||
      !("label" in m) ||
      typeof m.label !== "string" ||
      !("kind" in m) ||
      !(
        m.kind === "passkey" ||
        m.kind === "otp" ||
        m.kind === "securityKey" ||
        m.kind === "recovery"
      ) ||
      !("removable" in m) ||
      typeof m.removable !== "boolean" ||
      !("createdAt" in m) ||
      !(
        m.createdAt === null ||
        (typeof m.createdAt === "number" &&
          Number.isFinite(m.createdAt) &&
          m.createdAt >= 0 &&
          m.createdAt <= 8640000000000000)
      )
    )
      throw Error();
    return {
      id: m.id,
      label: m.label,
      kind: m.kind,
      removable: m.removable,
      createdAt: m.createdAt,
    };
  });
}

export function AccountMethods({
  t,
  locale,
  csrf,
}: {
  t: Dictionary["account"];
  locale: Locale;
  csrf: string;
}) {
  const [rows, setRows] = useState<CredentialMethod[] | null>(null);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    fetch("/api/account/methods", {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw Error();
        const next = methods(await response.json());
        if (active) {
          setRows(next);
          setError(false);
        }
      })
      .catch(() => {
        if (active) {
          setRows(null);
          setError(true);
        }
      })
      .finally(() => window.clearTimeout(timeout));
    return () => {
      active = false;
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [csrf, revision]);
  const kind = (row: CredentialMethod) =>
    row.kind === "passkey"
      ? t.methodPasskey
      : row.kind === "otp"
        ? t.methodOtp
        : row.kind === "securityKey"
          ? t.methodSecurityKey
          : t.methodRecovery;
  return (
    <section
      aria-labelledby="account-methods-title"
      className="mt-8 rounded-2xl border border-border bg-card p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="account-methods-title" className="text-xl font-semibold">
          {t.methodsTitle}
        </h2>
        <Button
          type="button"
          variant="outline"
          disabled={rows === null && !error}
          onClick={() => {
            setRows(null);
            setError(false);
            setRevision((v) => v + 1);
          }}
        >
          {t.methodsRefresh}
        </Button>
      </div>
      <p className="mt-3 text-sm text-muted-foreground">{t.methodsHelp}</p>
      {error ? (
        <div role="alert" className="mt-4">
          <p>{t.methodsUnavailable}</p>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setError(false);
              setRows(null);
              setRevision((v) => v + 1);
            }}
          >
            {t.methodsRetry}
          </Button>
        </div>
      ) : rows === null ? (
        <p role="status" className="mt-4">
          {t.methodsLoading}
        </p>
      ) : rows.length === 0 ? (
        <p className="mt-4">{t.methodsEmpty}</p>
      ) : (
        <ul className="mt-5 space-y-4">
          {rows.map((row) => (
            <li
              key={row.id}
              data-method-id={row.id}
              className="rounded-xl border border-border p-4"
            >
              <h3 className="font-semibold break-words">
                <bdi>{row.label || kind(row)}</bdi>
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {kind(row)}
                {row.createdAt !== null && (
                  <>
                    {" "}
                    · {t.methodCreated}{" "}
                    <time dateTime={new Date(row.createdAt).toISOString()}>
                      {new Intl.DateTimeFormat(
                        locale === "de" ? "de-CH" : "en-GB",
                        { dateStyle: "medium", timeStyle: "short" },
                      ).format(row.createdAt)}
                    </time>
                  </>
                )}
              </p>
              {row.removable ? (
                <details className="mt-3">
                  <summary className="min-h-11 cursor-pointer py-2 text-sm font-medium text-primary">
                    {t.methodRemove}
                  </summary>
                  <form
                    action="/api/account/remove"
                    method="post"
                    className="mt-3 space-y-4"
                  >
                    <input type="hidden" name="locale" value={locale} />
                    <input type="hidden" name="csrf" value={csrf} />
                    <input type="hidden" name="credentialId" value={row.id} />
                    <p className="text-sm text-muted-foreground">
                      {t.methodRemoveHelp}
                    </p>
                    <label className="flex items-start gap-3 text-sm">
                      <input
                        type="checkbox"
                        name="confirm"
                        value="yes"
                        required
                        className="mt-1"
                      />
                      <span>
                        {t.methodConfirm}{" "}
                        <bdi className="font-semibold">
                          {row.label || kind(row)}
                        </bdi>
                      </span>
                    </label>
                    <Button type="submit" variant="outline">
                      {t.methodRemoveContinue}
                    </Button>
                  </form>
                </details>
              ) : (
                <p className="mt-3 text-sm text-muted-foreground">
                  {t.methodProtected}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
