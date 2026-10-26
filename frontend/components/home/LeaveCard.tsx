"use client";

import { CalendarClock, Check, CheckCircle2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card } from "@/components/ui";
import { api } from "@/lib/api";
import { useToast } from "@/lib/toast";
import type { Leave } from "@/lib/types";
import { TeacherAwayDialog } from "./TeacherAwayDialog";

const day = (d: string) => new Date(`${d}T00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
const when = (l: Leave) => (l.start_date === l.end_date ? day(l.start_date) : `${day(l.start_date)} to ${day(l.end_date)}`);
const today = () => new Date().toISOString().slice(0, 10);

/** Coordinator / Admin Home: teachers' leave. Asked-for leave waits here; approving opens the cover plan
 *  (substitutes or cancel, per year). Leave already covered shows its summary. */
export function LeaveCard() {
  const showToast = useToast();
  const [items, setItems] = useState<Leave[] | null>(null);
  const [planning, setPlanning] = useState<{ leave: Leave } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    api.leaves().then(setItems).catch(() => setItems([]));
  }, []);
  useEffect(load, [load]);

  const decide = async (l: Leave, approve: boolean) => {
    setBusy(l.id);
    try {
      const out = await api.decideLeave(l.id, approve);
      showToast({ text: approve ? `Approved. Now plan cover for ${l.teacher_name}'s classes.` : "Leave declined. The teacher is told." });
      load();
      if (approve) setPlanning({ leave: out });
    } catch (e) {
      showToast({ text: e instanceof Error ? e.message : "That didn't work" });
    } finally {
      setBusy(null);
    }
  };

  // Waiting, approved without cover, and leave that is still running or ahead.
  const shown = (items ?? []).filter((l) => l.status === "pending" || (l.status === "approved" && l.end_date >= today()));
  const waiting = shown.filter((l) => l.status === "pending").length;

  return (
    <Card className="mb-6 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <CalendarClock size={16} aria-hidden /> Teacher leave
          {waiting > 0 && <Badge tone="warn">{waiting} waiting</Badge>}
        </h3>
      </div>
      {items === null ? null : shown.length === 0 ? (
        <p className="mt-2 text-sm text-muted">No leave coming up. Teachers ask for leave from their Home; you approve it here and the cover plan finds substitutes. Heard about it directly? Use Teacher away above.</p>
      ) : (
        <ul className="mt-3 divide-y divide-border">
          {shown.map((l) => (
            <li key={l.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
              <span className="min-w-0 flex-1">
                <span className="font-medium">{l.teacher_name}</span> <span className="text-muted">{when(l)}</span>
                <span className="block text-xs text-muted">
                  {l.status === "pending" ? `Asked by the teacher${l.reason ? `: ${l.reason}` : ""}`
                    : l.applied_at ? `Covered: ${l.plan_summary}` : `Approved${l.reason ? ` · ${l.reason}` : ""}. Cover not planned yet.`}
                </span>
              </span>
              {l.status === "pending" ? (
                <span className="flex gap-2">
                  <Button onClick={() => decide(l, false)} disabled={busy === l.id}><X size={14} aria-hidden /> Decline</Button>
                  <Button variant="primary" onClick={() => decide(l, true)} disabled={busy === l.id}><Check size={14} aria-hidden /> Approve and plan cover</Button>
                </span>
              ) : l.applied_at ? (
                <CheckCircle2 size={16} className="text-ok" aria-label="Covered" />
              ) : (
                <Button variant="primary" onClick={() => setPlanning({ leave: l })}>Plan cover</Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {planning && <TeacherAwayDialog leave={planning.leave} onClose={() => setPlanning(null)} onDone={load} />}
    </Card>
  );
}
