"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";
import { isRole, type Role } from "@/features/auth/permissions";
import { isInvitation, isSpace, type Space, type Invitation, type IssuedInvitation } from "@/features/spaces/contracts";
import { spaceMessages } from "@/features/spaces/messages";
import "./space.css";

export default function SpacePage() {
  const { locale, roles: myRoles, hasPermission } = useWorkspace();
  const t = spaceMessages[locale];
  const [space, setSpace] = useState<Space | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [issued, setIssued] = useState<IssuedInvitation | null>(null);
  const [link, setLink] = useState("");
  const [error, setError] = useState(false);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const canInvite = hasPermission("invitations:create");
  const owner = myRoles.includes("OWNER");

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/space", { signal: AbortSignal.timeout(10_000) });
      setError(false);
      const value: unknown = await response.json();
      if (!response.ok || !isSpace(value)) throw new Error();
      setSpace(value);
      if (hasPermission("roles:read")) {
        const result = await fetch("/api/rbac?resource=roles", { signal: AbortSignal.timeout(10_000) });
        const values: unknown = await result.json();
        if (!result.ok || !Array.isArray(values) || !values.every(isRole)) throw new Error();
        setRoles(values.filter((role) => role.key !== "OWNER"));
      }
      if (canInvite) {
        const result = await fetch("/api/space/invitations", { signal: AbortSignal.timeout(10_000) });
        const values: unknown = await result.json();
        if (!result.ok || !Array.isArray(values) || !values.every(isInvitation)) throw new Error();
        setInvitations(values);
      }
    } catch { setError(true); }
  // Permission sets come from the authenticated shell and are stable for this page.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canInvite]);
  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  async function mutate(path: string, method: string, body?: unknown) {
    if (pending) return;
    setPending(true); setError(false); setNotice("");
    try {
      const response = await fetch(path, { method, headers: { ...csrfHeader(), "Content-Type": "application/json" },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(15_000) });
      if (!response.ok) throw new Error();
      if (method === "POST") {
        const value: unknown = await response.json();
        if (!value || typeof value !== "object" || !("code" in value) || typeof value.code !== "string"
          || !/^[A-Za-z0-9_-]{43}$/.test(value.code) || !("id" in value) || typeof value.id !== "string"
          || !("expiresAt" in value) || typeof value.expiresAt !== "string"
          || !("roleKey" in value) || typeof value.roleKey !== "string"
          || !("maxUses" in value) || typeof value.maxUses !== "number") throw new Error();
        setIssued({ id: value.id, code: value.code, expiresAt: value.expiresAt, roleKey: value.roleKey, maxUses: value.maxUses });
        // Fragment avoids sending invitation credentials to servers or Referer headers.
        setLink(`${window.location.origin}/signup#invitation=${value.code}`);
      } else if (method === "PUT") setNotice(t.saved);
      await refresh();
    } catch { setError(true); }
    finally { setPending(false); }
  }

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void mutate("/api/space", "PUT", { name: data.get("name"), type: data.get("type"), defaultRoleKey: data.get("role") });
  }
  function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void mutate("/api/space/invitations", "POST", { roleId: data.get("role") || null,
      expiresInHours: Number(data.get("hours")), maxUses: Number(data.get("uses")) });
  }

  return <section className="settings-stage space-page"><div className="settings-card">
    <h1>{t.title}</h1><p>{t.description}</p><p>{t.role}: {myRoles.join(", ")}</p>
    {error && <p role="alert" className="auth-error">{t.error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!space && !error && <p role="status">{t.loading}</p>}
    <button type="button" onClick={() => void refresh()} disabled={pending}>{t.refresh}</button>
    {space && <>
      <form className="auth-form" onSubmit={save} key={`${space.id}-${space.name}-${space.type}-${space.defaultRoleKey}`}>
        <fieldset disabled={!owner || pending}>
          <label>{t.name}<input name="name" defaultValue={space.name} maxLength={120} required /></label>
          <label>{t.type}<select name="type" defaultValue={space.type}><option value="HOME">{t.home}</option><option value="BUSINESS">{t.business}</option></select></label>
          <label>{t.defaultRole}<select name="role" defaultValue={space.defaultRoleKey}>
            {roles.length ? roles.map((role) => <option key={role.id} value={role.key}>{role.name}</option>) : <option>{space.defaultRoleKey}</option>}
          </select></label>
          {owner && <button disabled={pending} type="submit">{t.save}</button>}
        </fieldset>
      </form>
      {hasPermission("users:read") && <p><Link href="/users">{t.members}</Link></p>}
      {space.type === "BUSINESS" && <aside><h2>{t.domain}</h2><p>{t.domainUnavailable}</p></aside>}
    </>}
    {canInvite && <section><h2>{t.invitations}</h2>
      <form className="auth-form" onSubmit={invite}>
        <label>{t.assignedRole}<select name="role"><option value="">{t.defaultRole}</option>{roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select></label>
        <label>{t.hours}<input name="hours" type="number" min={1} max={168} defaultValue={24} required /></label>
        <label>{t.uses}<input name="uses" type="number" min={1} max={20} defaultValue={1} required /></label>
        <button disabled={pending} type="submit">{pending ? t.pending : t.create}</button>
      </form>
      {issued && <div className="auth-form">
        <label>{t.code}<input readOnly value={issued.code} onFocus={(event) => event.currentTarget.select()} /></label>
        <label>{t.link}<input readOnly value={link} onFocus={(event) => event.currentTarget.select()} /></label>
        <p>{t.expires}: {new Date(issued.expiresAt).toLocaleString(locale)} · {issued.roleKey}</p>
        <p>{t.reachability}</p><button type="button" onClick={async () => { try { await navigator.clipboard.writeText(link); setNotice(t.copied); } catch { setError(true); } }}>{t.copy}</button>
      </div>}
      <ul>{invitations.map((invitation) => <li key={invitation.id}>
        <strong>{invitation.roleKey}</strong> · {t.statuses[invitation.status]} · {invitation.useCount}/{invitation.maxUses}
        <p>{t.expires}: {new Date(invitation.expiresAt).toLocaleString(locale)}</p>
        {invitation.status === "ACTIVE" && <button type="button" disabled={pending} onClick={() => {
          if (window.confirm(t.confirmRevoke)) void mutate(`/api/space/invitations/${invitation.id}`, "DELETE");
        }}>{t.revoke}</button>}
      </li>)}</ul>
    </section>}
  </div></section>;
}
