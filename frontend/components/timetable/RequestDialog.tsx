"use client";

import { ArrowRight, Loader2, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import type { MoveRequest } from "./useMoveEditor";

/** Teacher: ask the Department Coordinator for a permanent move. Nothing changes until they approve. */
export function RequestDialog({ request, subject, busy, onSend, onClose }: {
  request: MoveRequest; subject: string; busy: boolean; onSend: (reason: string) => void; onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const { session, option } = request;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true"
      aria-labelledby="request-title">
      <form
        className="w-full max-w-md rounded-xl border border-border bg-surface shadow-xl"
        onSubmit={(e) => {
          e.preventDefault();
          onSend(reason.trim());
        }}
      >
        <div className="border-b border-border px-5 py-4">
          <h2 id="request-title" className="font-semibold">Ask to move this lecture</h2>
          <p className="mt-1 text-sm text-muted">
            Permanent changes need your Department Coordinator. They see your request, check it and apply it.
          </p>
        </div>
        <div className="space-y-4 px-5 py-4 text-sm">
          <div>
            <p className="font-medium">{subject}</p>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded bg-surface-2 px-1.5 py-0.5">{session.day} {session.start}-{session.end}</span>
              <ArrowRight size={12} aria-hidden className="text-muted" />
              <span className="rounded bg-ok-soft px-1.5 py-0.5 text-ok">{option.day} {option.start}, every week</span>
            </div>
            {option.status === "repair" && (
              <p className="mt-2 text-xs text-warn">Other classes would move to make room; your Coordinator sees exactly which.</p>
            )}
          </div>
          <label className="block">
            <span className="text-xs font-medium">Reason (optional)</span>
            <textarea ref={ref} value={reason} onChange={(e) => setReason(e.target.value)} rows={3} maxLength={400}
              placeholder="e.g. Clinic duty every Monday morning"
              className="mt-1 w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm outline-none focus:border-accent" />
          </label>
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-4">
          <Button type="button" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button type="submit" variant="primary" disabled={busy}>
            {busy ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Send size={16} aria-hidden />} Send request
          </Button>
        </div>
      </form>
    </div>
  );
}
