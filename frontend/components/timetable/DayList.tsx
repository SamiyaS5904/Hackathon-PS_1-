"use client";

import clsx from "clsx";
import { useEffect, useState } from "react";
import { Badge, Card } from "@/components/ui";
import type { College, Occurrence, ViewKind, WeekOut } from "@/lib/types";

/** True on phone-sized screens (the wide grid becomes day-by-day cards there). */
export function useIsPhone(): boolean {
  const [phone, setPhone] = useState(false);
  useEffect(() => {
    const q = window.matchMedia("(max-width: 640px)");
    const on = () => setPhone(q.matches);
    on();
    q.addEventListener("change", on);
    return () => q.removeEventListener("change", on);
  }, []);
  return phone;
}

const pad = (n: number) => String(n).padStart(2, "0");
const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** One week on a phone: a card per day with the shown section's / teacher's / room's classes on real dates. */
export function DayList({ college, week, view, entityId, onSelect }: {
  college: College;
  week: WeekOut;
  view: ViewKind;
  entityId: string;
  onSelect?: (o: Occurrence) => void;
}) {
  const today = iso(new Date());
  const name = (id: string, list: { id: string; name: string }[]) => list.find((x) => x.id === id)?.name ?? "";
  const mine = (o: Occurrence) => view === "section" ? o.session.section_ids.includes(entityId)
    : view === "teacher" ? o.session.teacher_id === entityId : o.session.venue_id === entityId;
  return (
    <div className="space-y-2">
      {week.days.map((d) => {
        const items = week.occurrences.filter((o) => o.date === d.date && mine(o))
          .sort((a, b) => a.session.start.localeCompare(b.session.start));
        return (
          <Card key={d.date} className={clsx("p-3", d.date === today && "border-accent/50 ring-1 ring-accent/30")}>
            <p className="mb-1.5 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
              {d.label}{d.date === today && <Badge tone="accent">Today</Badge>}
            </p>
            {d.holiday ? <p className="text-sm text-muted">Holiday: {d.holiday}</p>
              : items.length === 0 ? <p className="text-sm text-muted">No classes</p> : (
                <ul className="divide-y divide-border">
                  {items.map((o) => {
                    const off = o.status === "cancelled" || o.status === "moved_out";
                    const row = (
                      <span className="flex w-full flex-wrap items-center gap-x-2 gap-y-0.5 py-1.5 text-left text-sm">
                        <span className="w-12 shrink-0 font-mono text-xs text-muted">{o.session.start}</span>
                        <span className={clsx("font-medium", off && "text-muted line-through")}>{name(o.session.subject_id, college.subjects)}</span>
                        <span className="text-xs text-muted">
                          {view === "section" ? name(o.session.teacher_id, college.teachers)
                            : o.session.section_ids.map((id) => name(id, college.sections)).join(" + ")}
                          {view !== "venue" && ` · ${name(o.session.venue_id, college.venues)}`}
                        </span>
                        {o.status !== "normal" && (
                          <Badge tone={o.status === "cancelled" ? "danger" : "warn"}>
                            {o.status === "cancelled" ? "Cancelled" : o.status === "moved_in" ? "Moved here" : "Moved"}
                          </Badge>
                        )}
                      </span>
                    );
                    return (
                      <li key={o.occurrence_id + o.status}>
                        {onSelect ? <button onClick={() => onSelect(o)} className="w-full hover:bg-surface-2">{row}</button> : row}
                      </li>
                    );
                  })}
                </ul>
              )}
          </Card>
        );
      })}
    </div>
  );
}
