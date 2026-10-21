"use client";

import { ArrowRight, Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";
import { Button } from "@/components/ui";
import type { Proposal } from "@/lib/types";

export function ProposalDialog({
  proposal,
  busy,
  onApply,
  onDiscard,
}: {
  proposal: Proposal;
  busy: boolean;
  onApply: () => void;
  onDiscard: () => void;
}) {
  const applyRef = useRef<HTMLButtonElement>(null);
  useEffect(() => applyRef.current?.focus(), []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onDiscard();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDiscard]);

  const delta =
    proposal.quality_before !== null && proposal.quality_after !== null
      ? proposal.quality_after - proposal.quality_before
      : null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true"
      aria-labelledby="proposal-title">
      <div className="w-full max-w-lg rounded-xl border border-border bg-surface shadow-xl">
        <div className="border-b border-border px-5 py-4">
          <h2 id="proposal-title" className="font-semibold">Review this change</h2>
          <p className="mt-1 text-sm text-muted">{proposal.message} Checked: no clashes.</p>
        </div>
        <ul className="max-h-80 divide-y divide-border overflow-auto px-5">
          {proposal.changes.map((c, i) => (
            <li key={c.session_id} className="py-3 text-sm">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium">{c.subject}</span>
                <span className="text-xs text-muted">{i === 0 ? "the class you moved" : "moved to make room"}</span>
              </div>
              <div className="text-xs text-muted">{c.sections}</div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded bg-danger-soft px-1.5 py-0.5 text-danger line-through decoration-danger/60">
                  {c.before}
                </span>
                <ArrowRight size={12} aria-hidden className="text-muted" />
                <span className="rounded bg-ok-soft px-1.5 py-0.5 text-ok">{c.after}</span>
              </div>
            </li>
          ))}
        </ul>
        <div className="flex items-center justify-between gap-3 border-t border-border px-5 py-4">
          <span className="text-xs text-muted">
            Quality {proposal.quality_before} → <b className="text-text">{proposal.quality_after}</b>
            {delta !== null && delta !== 0 && (
              <span className={delta > 0 ? "text-ok" : "text-warn"}> ({delta > 0 ? "+" : ""}{delta})</span>
            )}
          </span>
          <div className="flex gap-2">
            <Button onClick={onDiscard} disabled={busy}>
              Discard
            </Button>
            <Button ref={applyRef} variant="primary" onClick={onApply} disabled={busy}>
              {busy && <Loader2 size={16} className="animate-spin" aria-hidden />} Apply change
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
