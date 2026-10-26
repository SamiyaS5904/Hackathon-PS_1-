"use client";

import { CalendarClock, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card } from "@/components/ui";
import { api } from "@/lib/api";
import { useToast } from "@/lib/toast";
import type { Leave } from "@/lib/types";

const input = "w-full rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";
const day = (d: string) => new Date(`${d}T00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
const tomorrow = () => {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const STATUS = { pending: ["warn", "Waiting"], approved: ["ok", "Approved"], declined: ["danger", "Declined"], withdrawn: ["neutral", "Withdrawn"] } as const;

/** Teacher Home: ask for leave (the Department Coordinator approves and plans cover) and see what was decided. */
export function MyLeaveCard() {
  const showToast = useToast();
  const [items, setItems] = useState<Leave[] | null>(null);
  const [open, setOpen] = useState(false);
  const [from, setFrom] = useState(tomorrow());
  const [to, setTo] = useState(tomorrow());
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => { api.leaves().then(setItems).catch(() => setItems([])); }, []);
  useEffect(load, [load]);

  const ask = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.askLeave({ start_date: from, end_date: to, reason });
      showToast({ text: "Leave asked. Your Coordinator is told and plans cover for your classes." });
      setOpen(false);
      setReason("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't send it");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="mt-8 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold"><CalendarClock size={16} aria-hidden /> My leave</h2>
        {!open && <Button onClick={() => setOpen(true)}>Ask for leave</Button>}
      </div>
      {open && (
        <div className="mt-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-muted">From
              <input type="date" aria-label="From" className={`${input} mt-1`} value={from}
                onChange={(e) => { setFrom(e.target.value); if (to < e.target.value) setTo(e.target.value); }} />
            </label>
            <label className="text-xs text-muted">To
              <input type="date" aria-label="To" className={`${input} mt-1`} value={to} min={from} onChange={(e) => setTo(e.target.value)} />
            </label>
          </div>
          <label className="block text-xs text-muted">Reason
            <input aria-label="Reason" className={`${input} mt-1`} value={reason} maxLength={200} placeholder="e.g. Conference in Delhi"
              onChange={(e) => setReason(e.target.value)} />
          </label>
          {error && <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={ask} disabled={busy}>
              {busy && <Loader2 size={16} className="animate-spin" aria-hidden />} Send to my Coordinator
            </Button>
          </div>
        </div>
      )}
      {items && items.length > 0 ? (
        <ul className="mt-3 divide-y divide-border">
          {items.slice(0, 5).map((l) => {
            const [tone, text] = STATUS[l.status];
            return (
              <li key={l.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                <span className="flex-1">{l.start_date === l.end_date ? day(l.start_date) : `${day(l.start_date)} to ${day(l.end_date)}`}
                  <span className="block text-xs text-muted">{l.applied_at ? `Cover in place: ${l.plan_summary}` : l.reason || "No reason given"}</span></span>
                <Badge tone={tone}>{text}</Badge>
              </li>
            );
          })}
        </ul>
      ) : !open && items ? <p className="mt-2 text-sm text-muted">Away on some days? Ask here; your Coordinator finds substitutes for your classes.</p> : null}
    </Card>
  );
}
