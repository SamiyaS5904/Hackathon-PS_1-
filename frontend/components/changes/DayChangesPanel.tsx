"use client";

import { CalendarX2, Loader2, MoveRight, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { isStaff, useAuth } from "@/lib/auth";
import { useTimetable } from "@/lib/timetable-context";
import { useToast } from "@/lib/toast";
import type { Occurrence } from "@/lib/types";

const pad = (n: number) => String(n).padStart(2, "0");
const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
function monday(offsetWeeks: number): string {
  const d = new Date();
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7) + 7 * offsetWeeks);
  return iso(d);
}

/** One-day changes (cancelled or moved classes) this week and next. Staff and teachers can restore a class
 *  they may change; everyone sees only the classes they can see. */
export function DayChangesPanel() {
  const { role, member } = useAuth();
  const { college, setData } = useTimetable();
  const showToast = useToast();
  const [items, setItems] = useState<Occurrence[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const weeks = await Promise.all([api.week(monday(0)), api.week(monday(1))]);
      const today = iso(new Date());
      setItems(weeks.flatMap((w) => w.occurrences)
        // A move shows once, on the day it was moved from.
        .filter((o) => (o.status === "cancelled" || o.status === "moved_out") && o.date >= today)
        .sort((a, b) => (a.date + a.session.start).localeCompare(b.date + b.session.start)));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load this week's changes");
      setItems([]);
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const shown = useMemo(() => {
    if (!items || !college) return items;
    if (role !== "coordinator") return items;
    const mine = new Set(college.sections.filter((s) => s.department_id === member?.department_id).map((s) => s.id));
    return items.filter((o) => o.session.section_ids.some((id) => mine.has(id)));
  }, [items, college, role, member]);

  const canRestore = (o: Occurrence) => isStaff(role) || (role === "teacher" && o.session.teacher_id === member?.teacher_id);

  const restore = async (o: Occurrence) => {
    if (!o.override_id) return;
    setBusy(o.override_id);
    try {
      const out = await api.removeOverride(o.override_id);
      setData(out.timetable);
      showToast({ text: out.message, undoEntryId: out.timetable.last_change?.id,
        onUndone: (t) => { setData(t); load(); } });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't restore the class");
    } finally {
      setBusy(null);
    }
  };

  const name = (id: string, list: { id: string; name: string }[] | undefined) => list?.find((x) => x.id === id)?.name ?? "";
  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold">One-day changes, this week and next</h2>
      {error && <p role="alert" className="mb-2 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {!shown ? <Skeleton className="h-24 w-full" /> : shown.length === 0 ? (
        <Card className="p-6 text-center text-sm text-muted">
          No cancelled or moved classes coming up.
          {role !== "student" && (
            <span className="mt-3 block">
              <Link href="/timetable?mode=week"><Button>Open this week</Button></Link>
            </span>
          )}
        </Card>
      ) : (
        <ul className="space-y-2">
          {shown.map((o) => (
            <li key={o.occurrence_id}>
              <Card className="flex flex-wrap items-center gap-3 p-3">
                {o.status === "cancelled"
                  ? <CalendarX2 size={18} className="shrink-0 text-danger" aria-hidden />
                  : <MoveRight size={18} className="shrink-0 text-warn" aria-hidden />}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {name(o.session.subject_id, college?.subjects)}{" "}
                    <span className="font-normal text-muted">
                      {o.session.section_ids.map((id) => name(id, college?.sections)).join(" + ")}
                    </span>
                  </p>
                  <p className="text-xs text-muted">
                    {new Date(`${o.date}T00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}
                    {" "}{o.session.start} · {name(o.session.teacher_id, college?.teachers)} · {o.note}
                  </p>
                </div>
                <Badge tone={o.status === "cancelled" ? "danger" : "warn"}>{o.status === "cancelled" ? "Cancelled" : "Moved"}</Badge>
                {canRestore(o) && o.override_id && (
                  <Button onClick={() => restore(o)} disabled={busy !== null} className="h-8 px-2.5 text-xs">
                    {busy === o.override_id ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <RotateCcw size={13} aria-hidden />}
                    Restore usual time
                  </Button>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
