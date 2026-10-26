"use client";

import { CheckCircle2, AlertTriangle, Gauge, Clock } from "lucide-react";
import type { TimetableOut } from "@/lib/types";
import { qualityInWords } from "./TrustBar";

/** Timetable health. `compact` = one line at every width (the timetable page, where the grid is the hero). */
export function HealthStrip({ data, compact = false }: { data: TimetableOut; compact?: boolean }) {
  const clashes = data.violations.length;
  const score = data.quality?.score ?? 0;
  const tone = score >= 85 ? "text-ok" : score >= 70 ? "text-warn" : "text-danger";
  return (
    <>
    {/* Phones: one compact line, so the timetable itself is on the first screen. */}
    <p className={`mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm ${compact ? "" : "sm:hidden"}`} role="status">
      <span className="flex items-center gap-1">
        {clashes === 0 ? <CheckCircle2 size={15} className="text-ok" aria-hidden /> : <AlertTriangle size={15} className="text-danger" aria-hidden />}
        <b>{clashes === 0 ? "0 clashes" : `${clashes} clash${clashes === 1 ? "" : "es"}`}</b>
      </span>
      <span className="flex items-center gap-1"><Gauge size={15} className={tone} aria-hidden /> Quality <b>{score}/100</b></span>
      <span className="text-muted">{data.timetable.sessions.length} classes</span>
      {compact && <span className="text-muted">· checked by an independent validator</span>}
    </p>
    {!compact && <div className="mb-4 hidden grid-cols-2 gap-3 sm:grid lg:grid-cols-4">
      <Stat
        icon={clashes === 0 ? <CheckCircle2 size={18} className="text-ok" /> : <AlertTriangle size={18} className="text-danger" />}
        label="Clashes"
        value={clashes === 0 ? "0 clashes" : `${clashes} clash${clashes === 1 ? "" : "es"}`}
        hint="Checked by an independent validator"
      />
      <Stat icon={<Gauge size={18} className={tone} />} label="Quality" value={data.quality ? qualityInWords(data.quality).split(":")[0] : "–"}
        hint={data.quality ? `${qualityInWords(data.quality).split(": ")[1] ?? ""} (${score}/100)` : ""} />
      <Stat
        icon={<CheckCircle2 size={18} className="text-muted" />}
        label="Classes placed"
        value={String(data.timetable.sessions.length)}
        hint={data.timetable.lunches.length ? "Lunch for every section, every day" : "Clash-free"}
      />
      <Stat
        icon={<Clock size={18} className="text-muted" />}
        label="Built in"
        value={`${data.timetable.solve_seconds.toFixed(0)}s`}
        hint={data.timetable.status === "optimal" ? "The best possible arrangement" : "The best arrangement found in that time"}
      />
    </div>}
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
