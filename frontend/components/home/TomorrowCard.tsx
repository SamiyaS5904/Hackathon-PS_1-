"use client";

import { Moon, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Card } from "@/components/ui";
import { api } from "@/lib/api";
import { useChatPage } from "@/lib/chat-context";
import { useTimetable } from "@/lib/timetable-context";
import type { Leave, TodayReport } from "@/lib/types";
import { TeacherAwayDialog } from "./TeacherAwayDialog";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const pad = (n: number) => String(n).padStart(2, "0");
const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** The brief for the next working day (Coordinator / Admin Home), so cover is sorted the evening before:
 *  teachers on leave and whether their classes are covered, classes not happening or moved. */
export function TomorrowCard() {
  const { college } = useTimetable();
  const { ask } = useChatPage();
  const [report, setReport] = useState<TodayReport | null>(null);
  const [leaves, setLeaves] = useState<Leave[]>([]);
  const [planning, setPlanning] = useState<Leave | null>(null);

  const next = useMemo(() => {
    const d = new Date();
    for (let i = 1; i < 10; i++) {
      const x = new Date(d);
      x.setDate(d.getDate() + i);
      if (college?.days.includes(WEEKDAYS[x.getDay()])) return iso(x);
    }
    return null;
  }, [college]);

  const load = () => {
    if (!next) return;
    api.today(next).then(setReport).catch(() => setReport(null));
    api.leaves().then(setLeaves).catch(() => setLeaves([]));
  };
  useEffect(load, [next]);

  if (!next || !report) return null;
  const onLeave = leaves.filter((l) => l.status !== "declined" && l.status !== "withdrawn" && l.start_date <= next && l.end_date >= next);
  const uncovered = onLeave.filter((l) => !l.applied_at);
  const evening = new Date().getHours() >= 14;
  const brief = `Brief me on ${report.label}: who is on leave, which classes have no cover, what is cancelled or moved, and what I should fix tonight.`;

  return (
    <Card className={`mb-6 p-5 ${evening && uncovered.length ? "border-warn/50" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold"><Moon size={16} aria-hidden /> Tomorrow · {report.label}</h3>
        {uncovered.length > 0 && <Badge tone="warn">{uncovered.length} without cover</Badge>}
        <Button className="ml-auto" onClick={() => ask(brief)}><Sparkles size={14} aria-hidden /> Brief me</Button>
      </div>
      {!report.working ? (
        <p className="mt-2 text-sm text-muted">{report.holiday ? `Holiday: ${report.holiday}.` : "No classes."}</p>
      ) : (
        <>
          <p className="mt-2 text-sm text-muted">
            {report.classes_today} classes · {onLeave.length} teacher{onLeave.length === 1 ? "" : "s"} on leave ·{" "}
            {report.cancelled.length} not happening · {report.moved.length} moved
          </p>
          {onLeave.length > 0 && (
            <ul className="mt-2 divide-y divide-border">
              {onLeave.map((l) => (
                <li key={l.id} className="flex flex-wrap items-center gap-2 py-1.5 text-sm">
                  <span className="flex-1"><span className="font-medium">{l.teacher_name}</span>
                    <span className="text-muted"> · {l.applied_at ? `covered (${l.plan_summary})` : l.status === "pending" ? "leave waiting for you" : "no cover yet"}</span></span>
                  {!l.applied_at && <Button variant="primary" onClick={() => setPlanning(l)}>Plan cover</Button>}
                </li>
              ))}
            </ul>
          )}
          {onLeave.length === 0 && report.cancelled.length === 0 && <p className="mt-1 text-xs text-ok">All set for tomorrow.</p>}
        </>
      )}
      {planning && <TeacherAwayDialog leave={planning} onClose={() => setPlanning(null)} onDone={load} />}
    </Card>
  );
}
