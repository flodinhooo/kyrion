"use client";

import { Dialog } from "radix-ui";
import type { ReactNode } from "react";

export function ConfirmDialog({ open, title, description, confirmLabel, cancelLabel, pending, error, onOpenChange, onConfirm }: {
  open: boolean; title: string; description: ReactNode; confirmLabel: string; cancelLabel: string; pending?: boolean;
  onOpenChange: (open: boolean) => void; onConfirm: () => void;
  error?: string;
}) {
  return <Dialog.Root open={open} onOpenChange={(next) => { if (!pending) onOpenChange(next); }}>
    <Dialog.Portal>
      <Dialog.Overlay className="confirm-dialog-overlay" />
      <Dialog.Content className="confirm-dialog-content">
        <Dialog.Title>{title}</Dialog.Title>
        <Dialog.Description asChild><div>{description}</div></Dialog.Description>
        {error && <p role="alert">{error}</p>}
        <div className="confirm-dialog-actions"><Dialog.Close asChild><button disabled={pending}>{cancelLabel}</button></Dialog.Close><button className="danger" disabled={pending} onClick={onConfirm}>{confirmLabel}</button></div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
