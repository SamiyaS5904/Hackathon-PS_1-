"use client";

import { Badge, Card, PageHeader, Skeleton } from "@/components/ui";
import { useTimetable } from "@/lib/timetable-context";

export default function DataPage() {
  const { college, loading } = useTimetable();
  if (loading || !college) return <Skeleton className="mx-auto h-96 max-w-6xl" />;

  const dept = new Map(college.departments.map((d) => [d.id, d.short]));
  const shift = new Map(college.shifts.map((s) => [s.id, s.name]));

  // Shift wording only for colleges that run two shifts (set in the setup wizard).
  const twoShifts = college.shifts.length > 1;
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="College data"
        subtitle="Read-only for now. The setup wizard and Excel import arrive in a later stage."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="text-sm font-semibold">{college.shifts.length > 1 ? "Shifts" : "College day"}</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {college.shifts.map((s) => (
              <li key={s.id}>
                <span className="font-medium">{s.name}</span>{" "}
                <span className="text-muted">
                  {s.periods[0]?.start}–{s.periods.at(-1)?.end} · {s.periods.length} periods
                  {s.lunch ? ` · lunch chosen inside ${s.lunch.window_start}–${s.lunch.window_end}` : ""}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted">Labs are {college.lab_periods} back-to-back periods.</p>
        </Card>

        <Card className="p-5">
          <h2 className="text-sm font-semibold">Departments</h2>
          <ul className="mt-3 space-y-1.5 text-sm">
            {college.departments.map((d) => (
              <li key={d.id} className="flex justify-between">
                <span>{d.name}</span>
                <span className="text-muted">
                  {college.sections.filter((s) => s.department_id === d.id).length} sections ·{" "}
                  {college.teachers.filter((t) => t.department_id === d.id).length} teachers
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Table
        title="Rooms & labs"
        head={["Name", "Type", "Seats", "Owner", "Equipment"]}
        rows={college.venues.map((v) => [
          v.name,
          v.type,
          v.capacity,
          v.department_id ? dept.get(v.department_id) : <Badge tone="accent">Shared</Badge>,
          v.tags.join(", ") || "-",
        ])}
      />
      <Table
        title="Sections"
        head={["Section", "Department", "Year", "Students", ...(twoShifts ? ["Shift"] : []), "Lab batches"]}
        rows={college.sections.map((s) => [
          s.name,
          dept.get(s.department_id),
          s.year,
          s.strength,
          ...(twoShifts ? [shift.get(s.shift_id)] : []),
          s.batches.map((b) => `${b.name} (${b.strength})`).join(", ") || "-",
        ])}
      />
      <Table
        title="Subjects"
        head={["Code", "Name", "Department", "Year", "Lectures/week", "Labs/week"]}
        rows={college.subjects.map((s) => [
          s.code,
          s.name,
          dept.get(s.department_id),
          s.year,
          s.lectures_per_week,
          s.labs_per_week ? `${s.labs_per_week} (${s.lab_tag ?? "any lab"})` : "-",
        ])}
      />
      <Table
        title="Teachers"
        head={["Name", "Department", ...(twoShifts ? ["Shift"] : []), "Max periods/day"]}
        rows={college.teachers.map((t) => [
          t.name,
          dept.get(t.department_id),
          ...(twoShifts ? [t.shift_ids.map((id) => shift.get(id)).join(" + ")] : []),
          t.max_per_day,
        ])}
      />
    </div>
  );
}

function Table({ title, head, rows }: { title: string; head: string[]; rows: React.ReactNode[][] }) {
  return (
    <Card className="mt-4 overflow-hidden">
      <h2 className="border-b border-border px-5 py-3 text-sm font-semibold">
        {title} <span className="font-normal text-muted">({rows.length})</span>
      </h2>
      <div className="max-h-80 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface-2 text-left text-xs text-muted">
            <tr>
              {head.map((h) => (
                <th key={h} className="px-5 py-2 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-border">
                {r.map((c, j) => (
                  <td key={j} className="px-5 py-2">
                    {c}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
