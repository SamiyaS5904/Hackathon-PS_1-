"use client";

import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { College, ViewKind } from "@/lib/types";

/** "Show timetable for…": one box for any section, teacher or room. Type a few letters, pick, done. */
export function FindAny({ college, onPick }: { college: College; onPick: (view: ViewKind, id: string) => void }) {
  const [text, setText] = useState("");
  const options = useMemo(() => [
    ...college.sections.map((s) => ({ label: `${s.name} (section)`, view: "section" as const, id: s.id })),
    ...college.teachers.map((t) => ({ label: `${t.name} (teacher)`, view: "teacher" as const, id: t.id })),
    ...college.venues.map((v) => ({ label: `${v.name} (room)`, view: "venue" as const, id: v.id })),
  ], [college]);

  const choose = (value: string) => {
    setText(value);
    const hit = options.find((o) => o.label.toLowerCase() === value.trim().toLowerCase());
    if (hit) {
      onPick(hit.view, hit.id);
      setText("");
    }
  };

  return (
    <div className="flex min-w-[12rem] items-center gap-2 rounded-lg border border-border-strong bg-surface px-2.5 py-1.5">
      <Search size={14} className="text-muted" aria-hidden />
      <input list="find-any" value={text} onChange={(e) => choose(e.target.value)} placeholder="Show timetable for…"
        aria-label="Show the timetable of a section, teacher or room" className="w-full bg-transparent text-sm outline-none" />
      <datalist id="find-any">
        {options.map((o) => <option key={o.view + o.id} value={o.label} />)}
      </datalist>
    </div>
  );
}
