"use client";

import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";
import { PasswordChangeForm } from "@/components/password-change-form";
import { MemoryPanel } from "@/components/memory-panel";

export default function ProfilePage() {
  const { username, t } = useWorkspace();
  return (
    <section className="settings-stage">
      <div className="settings-card profile-card">
        <div className="profile-avatar">{username.slice(0, 1).toUpperCase()}</div>
        <p className="eyebrow">{t.profile}</p>
        <h1>{username}</h1>
        <p className="placeholder-copy">{t.profileDescription}</p>

        <div className="settings-grid">
          <div className="settings-link-card profile-placeholder">
            <Icons.user />
            <span><strong>{t.profileDetails}</strong><small>{t.profileDetailsPlaceholder}</small></span>
          </div>
          <MemoryPanel />
          <div className="settings-link-card profile-security-panel">
            <Icons.shield />
            <span><strong>{t.profileSecurity}</strong><small>{t.profileSecurityDescription}</small></span>
            <PasswordChangeForm />
          </div>
          <div className="settings-link-card profile-placeholder">
            <Icons.clock />
            <span><strong>{t.profileSessions}</strong><small>{t.profileSessionsPlaceholder}</small></span>
          </div>
        </div>

        <Link className="placeholder-action" href="/"><Icons.chat />{t.backToChat}</Link>
      </div>
    </section>
  );
}
