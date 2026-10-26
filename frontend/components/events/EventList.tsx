"use client";

import clsx from "clsx";
import { AlertTriangle, Check, DoorOpen, Loader2, X } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card } from "@/components/ui";
import { extraApi } from "@/lib/api";
import type { VenueEvent } from "@/lib/types";

const TONE = { pending: "warn", approved: "ok", declined: "danger", cancelled: "neutral" } as const;
const STATUS = { pending: "Waiting for approval", approved: "Approved", declined: "Declined", cancelled: "Cancelled" };

/** Room bookings for events, with the actions this person may take (approve / decline / cancel). */
export function EventList({ items, empty, onChange }: { items: VenueEvent[]; empty: string; onChange: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [declining, setDeclining] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const act = async (id: string, fn: () => Promise<unknown>) => {
    setBusy(id);
    setError(null);
    try {
      await fn();
      setDeclining(null);
      setNote("");
      onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work");
    } finally {
      setBusy(null);
    }
  };

  if (items.length === 0) {
    return <Card className="flex items-center gap-3 p-5 text-sm text-muted"><DoorOpen size={18} aria-hidden /> {empty}</Card>;
  }
  return (
    <div className="space-y-2">
      {error && <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {items.map((e) => (
        <Card key={e.id} className={clsx("p-4", (e.status === "cancelled" || e.status === "declined") && "opacity-70")}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{e.venue} · {e.label} · {e.start}-{e.end}</span>
                <Badge tone={TONE[e.status]}>{STATUS[e.status]}</Badge>
              </div>
              <p className="mt-1 text-sm">{e.title}{e.club ? ` · ${e.club}` : ""}</p>
              <p className="mt-1 text-xs text-muted">
                Booked by {e.requested_by_name} · {e.capacity} seats
                {e.status === "pending" ? ` · decided by the ${e.approver}` : e.decided_by ? ` · ${STATUS[e.status].toLowerCase()} by ${e.decided_by}` : ""}
                {e.note ? ` · Note: ${e.note}` : ""}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {e.can_decide && (
                <>
                  <Button variant="primary" disabled={busy === e.id} onClick={() => act(e.id, () => extraApi.approveVenueEvent(e.id))}>
                    {busy === e.id ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} aria-hidden />} Approve
                  </Button>
                  <Button disabled={busy === e.id} onClick={() => setDeclining(declining === e.id ? null : e.id)}>Decline</Button>
                </>
              )}
              {e.can_cancel && !e.can_decide && (
                <button onClick={() => act(e.id, () => extraApi.cancelVenueEvent(e.id))} disabled={busy === e.id}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted hover:bg-surface-2 hover:text-danger">
                  {busy === e.id ? <Loader2 size={13} className="animate-spin" /> : <X size={13} />} Cancel
                </button>
              )}
            </div>
          </div>
          {declining === e.id && (
            <div className="mt-3 flex flex-wrap items-end gap-2 border-t border-border pt-3">
              <label className="min-w-[12rem] flex-1 text-xs text-muted">Note for {e.requested_by_name} (optional)
                <input aria-label="Note" value={note} maxLength={300} onChange={(x) => setNote(x.target.value)}
                  placeholder="e.g. The hall is needed for exams that day"
                  className="mt-1 block w-full rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm" />
              </label>
              <Button disabled={busy === e.id} onClick={() => act(e.id, () => extraApi.declineVenueEvent(e.id, note))}>
                {busy === e.id && <Loader2 size={15} className="animate-spin" />} Decline request
              </Button>
            </div>
          )}
          {e.clash && (
            <p className="mt-3 flex items-center gap-2 rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn" role="alert">
              <AlertTriangle size={14} className="shrink-0" aria-hidden /> The timetable changed: {e.clash}. Pick another room.
            </p>
          )}
        </Card>
      ))}
    </div>
  );
}
