"use client";

import clsx from "clsx";
import { Printer } from "lucide-react";
import { useMemo, useState } from "react";
import { GenerateButton, GenerationProgress } from "@/components/timetable/GenerateButton";
import { HealthStrip } from "@/components/timetable/HealthStrip";
import { TimetableGrid } from "@/components/timetable/TimetableGrid";
import { Button, Card, PageHeader, Skeleton } from "@/components/ui";
import { useTimetable } from "@/lib/timetable-context";
import type { ViewKind } from "@/lib/types";

const VIEWS: { id: ViewKind; label: string }[] = [
  { id: "section", label: "Section" },
  { id: "teacher", label: "Teacher" },
  { id: "venue", label: "Room" },
];

export default function TimetablePage() {
  const { college, data, loading, error } = useTimetable();
  const [view, setView] = useState<ViewKind>("section");
  const [picked, setPicked] = useState<Record<ViewKind, string>>({ section: "", teacher: "", venue: "" });

  const options = useMemo(() => {
    if (!college) return [];
    const dept = new Map(college.departments.map((d) => [d.id, d.short]));
    const list =
      view === "section"
        ? college.sections.map((s) => ({ id: s.id, label: s.name, group: dept.get(s.department_id) ?? "" }))
        : view === "teacher"
          ? college.teachers.map((t) => ({ id: t.id, label: t.name, group: dept.get(t.department_id) ?? "" }))
          : college.venues.map((v) => ({
              id: v.id,
              label: `${v.name} (${v.capacity})`,
              group: v.department_id ? (dept.get(v.department_id) ?? "") : "Shared",
            }));
    const groups = new Map<string, typeof list>();
    for (const o of list) groups.set(o.group, [...(groups.get(o.group) ?? []), o]);
    return [...groups.entries()];
  }, [college, view]);

  const entityId = picked[view] || options[0]?.[1][0]?.id || "";

  const subtitle = useMemo(() => {
    if (!college || !entityId) return "";
    if (view === "section") {
      const s = college.sections.find((x) => x.id === entityId);
      const shift = college.shifts.find((x) => x.id === s?.shift_id);
      return s ? `${s.strength} students · ${shift?.name} shift · ${s.batches.length} lab batches` : "";
    }
    if (view === "teacher") {
      const t = college.teachers.find((x) => x.id === entityId);
      const n = data?.timetable.sessions.filter((x) => x.teacher_id === entityId).reduce((a, x) => a + x.length, 0);
      return t ? `${n ?? 0} periods a week · max ${t.max_per_day}/day · ${t.shift_ids.join(" + ")} shift` : "";
    }
    const v = college.venues.find((x) => x.id === entityId);
    const u = data?.quality?.venue_utilisation[entityId];
    return v ? `${v.type} · seats ${v.capacity}${u !== undefined ? ` · used ${(u * 100).toFixed(0)}% of the week` : ""}` : "";
  }, [college, data, view, entityId]);

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Timetable"
        subtitle={college ? `${college.name} · weekly timetable` : undefined}
        actions={
          <>
            {data && (
              <Button variant="ghost" onClick={() => window.print()} className="no-print">
                <Printer size={16} aria-hidden /> Print
              </Button>
            )}
            <GenerateButton />
          </>
        }
      />

      <GenerationProgress />
      {error && (
        <Card className="mb-4 border-danger/30 bg-danger-soft p-4 text-sm text-danger">{error}</Card>
      )}

      {loading || !college ? (
        <Skeleton className="h-[520px] w-full" />
      ) : !data ? (
        <EmptyState />
      ) : data.timetable.sessions.length === 0 ? (
        <Card className="p-6">
          <h2 className="font-medium">No timetable could be built</h2>
          <ul className="mt-2 list-disc pl-5 text-sm text-muted">
            {data.timetable.messages.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </Card>
      ) : (
        <>
          <HealthStrip data={data} />

          <div className="no-print mb-3 flex flex-wrap items-center gap-3">
            <div className="inline-flex rounded-lg border border-border bg-surface p-0.5" role="tablist" aria-label="View by">
              {VIEWS.map((v) => (
                <button
                  key={v.id}
                  role="tab"
                  aria-selected={view === v.id}
                  onClick={() => setView(v.id)}
                  className={clsx(
                    "rounded-md px-3 py-1.5 text-sm transition",
                    view === v.id ? "bg-accent-soft font-medium text-accent-text" : "text-muted hover:text-text",
                  )}
                >
                  {v.label}
                </button>
              ))}
            </div>
            <label className="sr-only" htmlFor="entity">
              Choose
            </label>
            <select
              id="entity"
              value={entityId}
              onChange={(e) => setPicked({ ...picked, [view]: e.target.value })}
              className="min-w-56 rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm"
            >
              {options.map(([group, items]) => (
                <optgroup key={group} label={group}>
                  {items.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <span className="text-sm text-muted">{subtitle}</span>
          </div>

          <TimetableGrid college={college} timetable={data.timetable} view={view} entityId={entityId} />
        </>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <Card className="flex flex-col items-center px-6 py-16 text-center">
      <h2 className="text-lg font-semibold">No timetable yet</h2>
      <p className="mt-2 max-w-md text-sm text-muted">
        Your college data is loaded. Generate a timetable: every class gets a slot, a teacher and a room with no clashes,
        then you can view it by section, teacher or room.
      </p>
      <div className="mt-6">
        <GenerateButton />
      </div>
    </Card>
  );
}
