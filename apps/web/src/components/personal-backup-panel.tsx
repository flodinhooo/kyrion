"use client";

import { FormEvent, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";

export function PersonalBackupPanel() {
  const { t } = useWorkspace();
  const [state,setState]=useState<"idle"|"working"|"error"|"mismatch"|"done">("idle");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form=event.currentTarget; const data=new FormData(form);
    const passphrase=String(data.get("passphrase")??"");
    if(passphrase!==data.get("confirmation")){setState("mismatch");return;}
    setState("working");
    try {
      const response=await fetch("/api/backups/personal",{method:"POST",headers:{"Content-Type":"application/json",...csrfHeader()},body:JSON.stringify({passphrase})});
      if(!response.ok) throw new Error("backup failed");
      const blob=await response.blob(); const url=URL.createObjectURL(blob); const link=document.createElement("a");
      link.href=url; link.download=`kyrion-personal-backup-${new Date().toISOString().slice(0,10)}.json`; link.click(); URL.revokeObjectURL(url);
      form.reset(); setState("done");
    } catch { setState("error"); }
  }
  return <div className="settings-link-card backup-panel"><strong>{t.backupTitle}</strong><small>{t.backupDescription}</small>
    <form onSubmit={submit}><label>{t.backupPassphrase}<input name="passphrase" type="password" minLength={12} maxLength={200} autoComplete="new-password" aria-describedby="backup-passphrase-requirements" required /></label>
      <p id="backup-passphrase-requirements" className="backup-requirements">{t.backupPassphraseRequirements}</p>
      <label>{t.backupPassphraseConfirm}<input name="confirmation" type="password" minLength={12} maxLength={200} autoComplete="new-password" required /></label>
      <p>{t.backupExclusions}</p><button disabled={state==="working"} type="submit">{state==="working"?t.backupCreating:t.backupCreate}</button></form>
    {state==="done"&&<p className="form-success" role="status">{t.backupCreated}</p>}{state==="mismatch"&&<p className="auth-error" role="alert">{t.backupPassphraseMismatch}</p>}{state==="error"&&<p className="auth-error" role="alert">{t.backupError}</p>}
  </div>;
}
