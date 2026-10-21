"use client";

import { CheckCircle2, AlertTriangle, Gauge, Clock } from "lucide-react";
import type { TimetableOut } from "@/lib/types";

export function HealthStrip({ data }: { data: TimetableOut }) {
  const clashes = data.violations.length;
  const score = data.quality?.score ?? 0;
  const tone = score >= 85 ? "text-ok" : score >= 70 ? "text-warn" : "text-danger";
  return (
    <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Stat
        icon={clashes === 0 ? <CheckCircle2 size={18} className="text-ok" /> : <AlertTriangle size={18} className="text-danger" />}
        label="Clashes"
        value={clashes === 0 ? "0 clashes" : `${clashes} problems`}
        hint="Checked by an independent validator"
      />
      <Stat icon={<Gauge size={18} className={tone} />} label="Quality" value={`${score}/100`} hint="Gaps, load, room fit" />
      <Stat
        icon={<CheckCircle2 size={18} className="text-muted" />}
        label="Classes placed"
        value={String(data.timetable.sessions.length)}
        hint={`${data.timetable.lunches.length} lunch slots chosen`}
      />
      <Stat
        icon={<Clock size={18} className="text-muted" />}
        label="Solved in"
        value={`${data.timetable.solve_seconds.toFixed(0)}s`}
        hint={data.timetable.status === "optimal" ? "Proven best" : "Best found in time"}
      />
    </div>
  );
}

function Stat({ icon, label, value, hint }: { icon: React.ReactNode; label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface px-4 py-3">
      <div className="flex items-center gap-2 text-xs text-muted">
        {icon}
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold tracking-tight">{value}</div>
      <div className="text-xs text-muted">{hint}</div>
    </div>
  );
}
