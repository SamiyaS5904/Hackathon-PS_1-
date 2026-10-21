"use client";

import { AlertTriangle, ArrowRight, CheckCircle2, Circle, Info, Loader2, RefreshCw, Settings2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { InsightsCard } from "@/components/chat/InsightsCard";
import { GenerateButton, GenerationProgress } from "@/components/timetable/GenerateButton";
import { HealthStrip } from "@/components/timetable/HealthStrip";
import { Button, Card, ErrorCard, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { isStaff, useAuth } from "@/lib/auth";
import { useTimetable } from "@/lib/timetable-context";
import type { DepartmentReadiness } from "@/lib/types";

export default function Dashboard() {
  const { college, data, precheck, loading, error, reload } = useTimetable();
  const { role } = useAuth();
  const router = useRouter();
  const [sampleBusy, setSampleBusy] = useState(false);
  const [readiness, setReadiness] = useState<DepartmentReadiness[] | null>(null);

  useEffect(() => {
    if (isStaff(role) && college) api.readiness().then(setReadiness).catch(() => setReadiness(null));
  }, [role, college]);

  // Teachers and students go straight to their own timetable.
  useEffect(() => {
    if (role && !isStaff(role)) router.replace("/timetable");
  }, [role, router]);

  const loadSample = async () => {
    setSampleBusy(true);
    try {
      await api.loadSample();
      await reload();
    } finally {
      setSampleBusy(false);
    }
  };

  if (loading || !college) {
    return (
      <div className="mx-auto max-w-5xl space-y-4">
        {error && !loading && <ErrorCard message={error} onRetry={reload} />}
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-36 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  const problems = precheck?.problems ?? [];
  const warnings = [...(precheck?.warnings ?? [])];
  const hasTimetable = !!data && data.timetable.sessions.length > 0;

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Dashboard" subtitle={college.name} />
      <GenerationProgress />
      {error && <ErrorCard message={error} onRetry={reload} />}

      {/* Core first: the next step is always the first thing on the page. */}
      <Card className="mb-6 p-6">
        <p className="text-xs font-medium uppercase tracking-wide text-accent-text">Next step</p>
        {college.sections.length === 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="mt-1 text-lg font-semibold">
                {college.departments.length === 0 ? "Set up your college" : "Departments are adding their data"}
              </h2>
              <p className="mt-1 max-w-xl text-sm text-muted">
                {college.departments.length === 0
                  ? "Answer a few questions (shifts, periods, lunch, holidays, departments). Or load a realistic sample college (4 departments, 2 shifts, 12 sections) to try everything first."
                  : "Each Department Coordinator downloads their Excel sheet, fills it in, uploads it and marks the department Ready."}
              </p>
            </div>
            {role === "admin" && (
              <div className="flex flex-wrap gap-2">
                <Button onClick={loadSample} disabled={sampleBusy}>
                  {sampleBusy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />} Load sample college
                </Button>
                <Link href={college.departments.length === 0 ? "/setup" : "/departments"}>
                  <Button variant="primary"><Settings2 size={16} /> {college.departments.length === 0 ? "Start setup" : "Open departments"}</Button>
                </Link>
              </div>
            )}
          </div>
        ) : problems.length > 0 ? (
          <>
            <h2 className="mt-1 text-lg font-semibold">Fix {problems.length} data problem(s) before generating</h2>
            <ul className="mt-3 space-y-1.5 text-sm">
              {problems.map((p) => (
                <li key={p} className="flex gap-2 text-danger">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden /> {p}
                </li>
              ))}
            </ul>
          </>
        ) : data?.stale ? (
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="mt-1 flex items-center gap-2 text-lg font-semibold"><RefreshCw size={18} className="text-warn" /> College data changed</h2>
              <p className="mt-1 max-w-xl text-sm text-muted">
                Sections, teachers, rules or settings changed after the current timetable was made. Regenerate so the
                timetable matches; editing the old one is paused until then.
              </p>
            </div>
            {role === "admin" ? <GenerateButton label="Regenerate timetable" /> : <span className="text-sm text-muted">The College Admin regenerates the timetable.</span>}
          </div>
        ) : hasTimetable ? (
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="mt-1 text-lg font-semibold">Your timetable is ready</h2>
              <p className="mt-1 text-sm text-muted">
                Review it by section, teacher or room, and drag any class to change it safely.
              </p>
            </div>
            <Link href="/timetable">
              <Button variant="primary">
                Open timetable <ArrowRight size={16} aria-hidden />
              </Button>
            </Link>
          </div>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="mt-1 text-lg font-semibold">Generate your first timetable</h2>
              <p className="mt-1 text-sm text-muted">
                All data checks passed. Generation takes under a minute.
              </p>
            </div>
            {role === "admin" ? (
              <GenerateButton />
            ) : (
              <span className="text-sm text-muted">The College Admin generates the timetable.</span>
            )}
          </div>
        )}
      </Card>

      {hasTimetable && data && !data.stale && <HealthStrip data={data} />}

      {hasTimetable && data && !data.stale && (
        <InsightsCard revision={`${college.revision}-${data.quality?.score}-${data.timetable.sessions.length}`} />
      )}

      {readiness && readiness.length > 0 && (
        <Card className="mb-4 p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Departments ready: {readiness.filter((d) => d.ready).length} of {readiness.length}</h3>
            <Link href="/departments" className="text-xs text-accent-text hover:underline">Open departments</Link>
          </div>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {readiness.map((d) => (
              <li key={d.department_id}>
                <Link href={`/departments/${d.department_id}`} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-surface-2">
                  {d.ready ? <CheckCircle2 size={16} className="text-ok" /> : <Circle size={16} className="text-muted" />}
                  <span className="flex-1 truncate">{d.name}</span>
                  <span className="text-xs text-muted">
                    {d.ready ? "Ready" : d.without_teacher ? `${d.without_teacher} without teacher` : d.sections ? "In progress" : "No data yet"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="p-5">
          <h3 className="text-sm font-semibold">College at a glance</h3>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
            {[
              ["Departments", college.departments.length],
              ["Sections", college.sections.length],
              ["Teachers", college.teachers.length],
              ["Rooms & labs", college.venues.length],
              ["Shifts", college.shifts.map((s) => s.name).join(", ")],
              ["Working days", college.days.length],
            ].map(([k, v]) => (
              <div key={String(k)}>
                <dt className="text-xs text-muted">{k}</dt>
                <dd className="font-medium">{v}</dd>
              </div>
            ))}
          </dl>
        </Card>

        {hasTimetable && data?.quality ? (
          <Card className="p-5">
            <h3 className="text-sm font-semibold">Why the quality score is {data.quality.score}</h3>
            <ul className="mt-3 space-y-2 text-sm">
              {data.quality.items.map((i) => (
                <li key={i.key} className="flex items-start justify-between gap-3">
                  <span>
                    {i.label}
                    <span className="block text-xs text-muted">{i.detail}</span>
                  </span>
                  <span className="shrink-0 font-mono text-xs text-muted">−{i.penalty}</span>
                </li>
              ))}
            </ul>
          </Card>
        ) : (
          <Card className="p-5">
            <h3 className="text-sm font-semibold">What the generator guarantees</h3>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted">
              <li>No teacher, room or student group is ever double-booked</li>
              <li>Rooms fit the class size and type (labs in labs)</li>
              <li>Labs run as back-to-back periods, batches in parallel</li>
              <li>Shifts, breaks and a lunch slot inside the mess window</li>
            </ul>
          </Card>
        )}
      </div>

      {warnings.length > 0 && (
        <Card className="mt-4 p-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <Info size={16} className="text-warn" aria-hidden /> Good to know
          </h3>
          <ul className="mt-2 space-y-1.5 text-sm text-muted">
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
