"use client";

import { CheckCircle2, AlertTriangle, Gauge, Clock } from "lucide-react";
import type { TimetableOut } from "@/lib/types";

export function HealthStrip({ data }: { data: TimetableOut }) {
  const clashes = data.violations.length;
  const score = data.quality?.score ?? 0;
  const tone = score >= 85 ? "text-ok" : score >= 70 ? "text-warn" : "text-danger";
  return (
    <>
    {/* Phones: one compact line, so the timetable itself is on the first screen. */}
    <p className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm sm:hidden" role="status">
      <span className="flex items-center gap-1">
        {clashes === 0 ? <CheckCircle2 size={15} className="text-ok" aria-hidden /> : <AlertTriangle size={15} className="text-danger" aria-hidden />}
        <b>{clashes === 0 ? "0 clashes" : `${clashes} problems`}</b>
      </span>
      <span className="flex items-center gap-1"><Gauge size={15} className={tone} aria-hidden /> Quality <b>{score}/100</b></span>
      <span className="text-muted">{data.timetable.sessions.length} classes</span>
    </p>
    <div className="mb-4 hidden grid-cols-2 gap-3 sm:grid lg:grid-cols-4">
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
        hint={data.timetable.lunches.length ? "Lunch for every section, every day" : "Clash-free"}
      />
      <Stat
        icon={<Clock size={18} className="text-muted" />}
        label="Solved in"
        value={`${data.timetable.solve_seconds.toFixed(0)}s`}
        hint={data.timetable.status === "optimal" ? "Proven best" : "Best found in time"}
      />
    </div>
    </>
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
