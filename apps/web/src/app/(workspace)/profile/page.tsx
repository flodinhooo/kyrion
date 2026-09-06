"use client";

import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";
import { PasswordChangeForm } from "@/components/password-change-form";
import { MemoryPanel } from "@/components/memory-panel";
import { ActiveSessionsPanel } from "@/components/active-sessions-panel";
import { InvitationPanel } from "@/components/invitation-panel";
import { RetentionPolicyPanel } from "@/components/retention-policy-panel";
import { PersonalBackupPanel } from "@/components/personal-backup-panel";

export default function ProfilePage() {
  const { username, t } = useWorkspace();
  return (
    <section className="settings-stage">
      <div className="settings-card profile-card">
        <header className="profile-hero">
          <div className="profile-avatar">{username.slice(0, 1).toUpperCase()}</div>
          <div><p className="eyebrow">{t.profile}</p><h1>{username}</h1><p>{t.profileDescription}</p></div>
        </header>

        <nav className="profile-section-nav" aria-label={t.profile}>
          <a href="#backup">{t.backupTitle}</a><a href="#security">{t.profileSecurity}</a><a href="#memory">{t.memoryTitle}</a>
        </nav>

        <section className="profile-section profile-backup-section" id="backup">
          <div className="profile-section-heading"><Icons.shield /><div><p className="eyebrow">{t.backupTitle}</p><h2>{t.backupDescription}</h2></div></div>
          <div className="profile-two-column"><PersonalBackupPanel /><RetentionPolicyPanel /></div>
        </section>

        <section className="profile-section" id="security">
          <div className="profile-section-heading"><Icons.shield /><div><p className="eyebrow">{t.profileSecurity}</p><h2>{t.profileSecurityDescription}</h2></div></div>
          <div className="profile-two-column">
            <div className="settings-link-card profile-security-panel"><span><strong>{t.changePassword}</strong><small>{t.profileSecurityDescription}</small></span><PasswordChangeForm /></div>
            <ActiveSessionsPanel />
            <InvitationPanel />
          </div>
        </section>

        <section className="profile-section" id="memory">
          <div className="profile-section-heading"><Icons.user /><div><p className="eyebrow">{t.memoryTitle}</p><h2>{t.memoryDescription}</h2></div></div>
          <MemoryPanel />
        </section>

        <Link className="placeholder-action" href="/">{t.home}</Link>
      </div>
    </section>
  );
}
