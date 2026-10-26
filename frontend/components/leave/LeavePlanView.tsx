"use client";

import { CheckCircle2, Loader2, ShieldCheck, UserCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { useTimetableOptional } from "@/lib/timetable-context";
import { useToast } from "@/lib/toast";
import type { CoverAction, LeaveApplied, LeavePlan, PlanItem } from "@/lib/types";

const KEEP = "keep";
const CANCEL = "cancel";
const select = "w-full rounded-lg border border-border-strong bg-surface px-2 py-1 text-sm";
const key = (i: PlanItem) => `${i.session_id}@${i.date}`;

/** The cover plan for a teacher's leave: per year "find substitutes" or "cancel", per class the substitute
 *  (ranked, each already checked to be free) or cancel / leave as it is. Nothing changes until Apply. */
export function LeavePlanView({ teacherId, from, to, reason, leaveId, initialActions, via = "app", compact = false, onApplied }: {
  teacherId: string;
  from: string;
  to: string;
  reason: string;
  leaveId?: string;
  initialActions?: Record<number, CoverAction>;
  via?: "app" | "chatbot";
  compact?: boolean; // narrow place (the chat panel): one column
  onApplied?: (out: LeaveApplied) => void;
}) {
  // Works inside the chat panel too, which can be open on pages without the timetable.
  const reload = useTimetableOptional()?.reload ?? (async () => {});
  const showToast = useToast();
  const [actions, setActions] = useState<Record<number, CoverAction>>(initialActions ?? {});
  const [plan, setPlan] = useState<LeavePlan | null>(null);
  const [pick, setPick] = useState<Record<string, string>>({}); // per class: teacher id | "cancel" | "keep"
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    if (!teacherId || !from || !to || to < from) return;
    let live = true;
    setPlan(null);
    setError(null);
    api.planLeave({ teacher_id: teacherId, start_date: from, end_date: to, actions })
      .then((p) => {
        if (!live) return;
        setPlan(p);
        setPick(Object.fromEntries(p.items.map((i) => [key(i), i.action === "substitute" && i.teacher_id ? i.teacher_id : CANCEL])));
      })
      .catch((e) => live && setError(e instanceof Error ? e.message : "Couldn't make the plan"));
    return () => { live = false; };
  }, [teacherId, from, to, actions]);

  const byDate = useMemo(() => {
    const out: [string, PlanItem[]][] = [];
    for (const i of plan?.items ?? []) {
      const last = out[out.length - 1];
      if (last && last[0] === i.day_label) last[1].push(i);
      else out.push([i.day_label, [i]]);
    }
    return out;
  }, [plan]);

  const chosen = (plan?.items ?? []).filter((i) => pick[key(i)] !== KEEP);
  const covered = chosen.filter((i) => pick[key(i)] !== CANCEL).length;

  const apply = async () => {
    if (!plan) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api.applyLeave({
        leave_id: leaveId, teacher_id: teacherId, start_date: from, end_date: to, reason, via,
        choices: chosen.map((i) => {
          const p = pick[key(i)];
          return { session_id: i.session_id, date: i.date, action: p === CANCEL ? "cancel" : "substitute",
            teacher_id: p === CANCEL ? null : p };
        }),
      });
      await reload();
      setDone(out.message);
      showToast({ text: out.message, undoEntryId: out.entry_id, onUndone: () => { void reload(); } });
      onApplied?.(out);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't apply the plan");
    } finally {
      setBusy(false);
    }
  };

  if (done) return <p className="flex items-start gap-2 rounded-lg bg-ok-soft px-3 py-2 text-sm text-ok"><CheckCircle2 size={16} className="mt-0.5 shrink-0" aria-hidden /> {done}</p>;
  if (error && !plan) return <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!plan) return <p className="flex items-center gap-2 text-sm text-muted"><Loader2 size={14} className="animate-spin" aria-hidden /> Finding their classes and who is free to cover them…</p>;

  return (
    <div className="space-y-3">
      <p className="text-sm">{plan.summary}</p>
      {plan.years.length > 0 && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="What to do per year">
          {plan.years.map((y) => {
            const a = actions[y] ?? "substitute";
            return (
              <div key={y} className="flex items-center gap-1 rounded-lg border border-border px-2 py-1 text-xs">
                <span className="font-medium">Year {y}:</span>
                {(["substitute", "cancel"] as const).map((v) => (
                  <button key={v} type="button" aria-pressed={a === v}
                    onClick={() => setActions((s) => ({ ...s, [y]: v }))}
                    className={`rounded px-2 py-0.5 ${a === v ? "bg-accent text-white dark:text-bg" : "text-muted hover:bg-surface-2"}`}>
                    {v === "substitute" ? "Substitutes" : "Cancel"}
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      )}
      {byDate.map(([label, items]) => (
        <div key={label}>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
          <ul className="divide-y divide-border rounded-lg border border-border">
            {items.map((i) => {
              const k = key(i);
              const p = pick[k];
              const opt = i.options.find((o) => o.teacher_id === p);
              return (
                <li key={k} className={`grid gap-2 px-3 py-2 text-sm ${compact ? "" : "sm:grid-cols-[1fr_14rem] sm:items-center"}`}>
                  <span className="min-w-0">
                    <span className="font-medium">{i.subject}</span> <span className="text-muted">{i.sections}</span>
                    <span className="block text-xs text-muted">{i.start}-{i.end} · {i.venue}
                      {opt ? ` · ${opt.why}` : i.note ? ` · ${i.note}` : ""}</span>
                  </span>
                  <select aria-label={`What happens to ${i.subject} on ${i.day_label}`} className={select} value={p}
                    onChange={(e) => setPick((s) => ({ ...s, [k]: e.target.value }))}>
                    {i.options.map((o) => <option key={o.teacher_id} value={o.teacher_id}>Substitute: {o.name}</option>)}
                    <option value={CANCEL}>Cancel this class</option>
                    <option value={KEEP}>Leave it as it is</option>
                  </select>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {plan.problems.map((p) => <p key={p} className="text-xs text-warn">{p}</p>)}
      {error && <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs text-muted">
          <ShieldCheck size={14} className="text-ok" aria-hidden /> Every substitute is checked to be free. Students, teachers and you are told.
        </span>
        <Button variant="primary" onClick={apply} disabled={busy || (plan.items.length > 0 && chosen.length === 0)}>
          {busy ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <UserCheck size={16} aria-hidden />}
          {plan.items.length === 0 ? "Save leave" : `Apply: ${covered} substitute${covered === 1 ? "" : "s"}, ${chosen.length - covered} cancelled`}
        </Button>
      </div>
    </div>
  );
}
