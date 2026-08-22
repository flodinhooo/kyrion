"use client";

import { FormEvent, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";

export function PersonalBackupPanel() {
  const { t } = useWorkspace();
  const [state,setState]=useState<"idle"|"working"|"error"|"mismatch"|"done">("idle");
  const [preview,setPreview]=useState<{createdAt:string;conversations:number;messages:number;memories:number}|null>(null);
  const [importSource,setImportSource]=useState<{envelope:unknown;passphrase:string}|null>(null);
  const [confirmation,setConfirmation]=useState("");
  const [importResult,setImportResult]=useState<{conversationsImported:number;conversationsSkipped:number;messagesImported:number;memoriesImported:number;memoriesSkipped:number}|null>(null);
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
  async function previewBackup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data=new FormData(event.currentTarget); const file=data.get("backup");
    if(!(file instanceof File)){setState("error");return;} setState("working"); setPreview(null);
    try{
      const envelope:unknown=JSON.parse(await file.text());
      const response=await fetch("/api/backups/personal/preview",{method:"POST",headers:{"Content-Type":"application/json",...csrfHeader()},body:JSON.stringify({envelope,passphrase:data.get("importPassphrase")})});
      const value=await response.json() as {createdAt?:unknown;conversations?:unknown;messages?:unknown;memories?:unknown};
      if(!response.ok||typeof value.createdAt!=="string"||typeof value.conversations!=="number"||typeof value.messages!=="number"||typeof value.memories!=="number")throw new Error("preview failed");
      setPreview(value as {createdAt:string;conversations:number;messages:number;memories:number}); setImportSource({envelope,passphrase:String(data.get("importPassphrase"))}); setState("idle");
    }catch{setState("error");}
  }
  async function importBackup(){
    if(!importSource||confirmation!=="IMPORT")return;setState("working");
    try{const response=await fetch("/api/backups/personal/import",{method:"POST",headers:{"Content-Type":"application/json",...csrfHeader()},body:JSON.stringify({...importSource,confirmation})});const value=await response.json();if(!response.ok)throw new Error("import failed");setImportResult(value);setState("idle");setImportSource(null);}
    catch{setState("error");}
  }
  return <div className="settings-link-card backup-panel"><strong>{t.backupTitle}</strong><small>{t.backupDescription}</small>
    <form onSubmit={submit}><label>{t.backupPassphrase}<input name="passphrase" type="password" minLength={12} maxLength={200} autoComplete="new-password" aria-describedby="backup-passphrase-requirements" required /></label>
      <p id="backup-passphrase-requirements" className="backup-requirements">{t.backupPassphraseRequirements}</p>
      <label>{t.backupPassphraseConfirm}<input name="confirmation" type="password" minLength={12} maxLength={200} autoComplete="new-password" required /></label>
      <p>{t.backupExclusions}</p><button disabled={state==="working"} type="submit">{state==="working"?t.backupCreating:t.backupCreate}</button></form>
    {state==="done"&&<p className="form-success" role="status">{t.backupCreated}</p>}{state==="mismatch"&&<p className="auth-error" role="alert">{t.backupPassphraseMismatch}</p>}{state==="error"&&<p className="auth-error" role="alert">{t.backupError}</p>}
    <div className="backup-preview-divider"><strong>{t.backupPreviewTitle}</strong><small>{t.backupPreviewDescription}</small></div>
    <form onSubmit={previewBackup}><label>{t.backupFile}<input name="backup" type="file" accept="application/json,.json" required /></label>
      <label>{t.backupPassphrase}<input name="importPassphrase" type="password" minLength={12} maxLength={200} required /></label>
      <button disabled={state==="working"} type="submit">{t.backupPreview}</button></form>
    {preview&&<div className="backup-preview-result" role="status"><strong>{t.backupPreviewReady}</strong><span>{t.backupPreviewConversations}: {preview.conversations}</span><span>{t.backupPreviewMessages}: {preview.messages}</span><span>{t.backupPreviewMemories}: {preview.memories}</span></div>}
    {importSource&&<div className="backup-import-confirm"><p>{t.backupImportWarning}</p><label>{t.backupImportConfirmation}<input value={confirmation} onChange={event=>setConfirmation(event.target.value)} autoComplete="off" /></label><button type="button" disabled={confirmation!=="IMPORT"||state==="working"} onClick={()=>void importBackup()}>{t.backupImport}</button></div>}
    {importResult&&<div className="backup-import-result" role="status"><strong>{t.backupImportComplete}</strong><span>{t.backupImportedConversations}: {importResult.conversationsImported}</span><span>{t.backupSkippedConversations}: {importResult.conversationsSkipped}</span><span>{t.backupImportedMessages}: {importResult.messagesImported}</span><span>{t.backupImportedMemories}: {importResult.memoriesImported}</span><span>{t.backupSkippedMemories}: {importResult.memoriesSkipped}</span></div>}
  </div>;
}
