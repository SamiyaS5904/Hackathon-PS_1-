"use client";

import { Loader2, Send } from "lucide-react";
import { useState } from "react";
import { FormError } from "@/components/Field";
import { Button } from "@/components/ui";
import { extraApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { College, NoticeKind } from "@/lib/types";

const input = "rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";
const inDays = (n: number) => {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** Coordinator (own department) / College Admin (any department or everyone): write a notice. */
export function NoticeComposer({ college, onPosted, onClose }: { college: College; onPosted: () => void; onClose: () => void }) {
  const { role, member } = useAuth();
  const admin = role === "admin";
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [kind, setKind] = useState<NoticeKind>("dept_students");
  const [dept, setDept] = useState(admin ? college.departments[0]?.id ?? "" : member?.department_id ?? "");
  const sections = college.sections.filter((s) => s.department_id === dept);
  const years = [...new Set(sections.map((s) => s.year))].sort();
  const [year, setYear] = useState<number | null>(null);
  const [section, setSection] = useState("");
  const [expires, setExpires] = useState(inDays(3));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      await extraApi.postNotice({
        title, body, kind, expires, department_id: kind === "college" ? null : dept,
        year: kind === "year" ? year ?? years[0] ?? null : null, section_id: kind === "section" ? section || sections[0]?.id || null : null,
      });
      onPosted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't post the notice");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3 space-y-3 border-t border-border pt-3">
      <input aria-label="Notice" className={`${input} w-full font-medium`} value={title} maxLength={160}
        placeholder="e.g. Project review for 3rd year on Friday at 2 pm" onChange={(e) => setTitle(e.target.value)} />
      <textarea aria-label="Details" className={`${input} w-full`} rows={2} value={body} maxLength={1000}
        placeholder="Details (optional)" onChange={(e) => setBody(e.target.value)} />
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-muted">For
          <select aria-label="For" className={`${input} mt-1 block`} value={kind} onChange={(e) => setKind(e.target.value as NoticeKind)}>
            <option value="dept_students">Students of the department</option>
            <option value="year">Students of one year</option>
            <option value="section">One section</option>
            <option value="dept_teachers">Teachers of the department</option>
            {admin && <option value="college">Everyone in the college</option>}
          </select>
        </label>
        {admin && kind !== "college" && (
          <label className="text-xs text-muted">Department
            <select aria-label="Department" className={`${input} mt-1 block`} value={dept} onChange={(e) => { setDept(e.target.value); setSection(""); setYear(null); }}>
              {college.departments.map((d) => <option key={d.id} value={d.id}>{d.short}</option>)}
            </select>
          </label>
        )}
        {kind === "year" && (
          <label className="text-xs text-muted">Year
            <select aria-label="Year" className={`${input} mt-1 block`} value={year ?? years[0] ?? ""} onChange={(e) => setYear(Number(e.target.value))}>
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </label>
        )}
        {kind === "section" && (
          <label className="text-xs text-muted">Section
            <select aria-label="Section" className={`${input} mt-1 block`} value={section || sections[0]?.id || ""} onChange={(e) => setSection(e.target.value)}>
              {sections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
        )}
        <label className="text-xs text-muted">Show until
          <input type="date" aria-label="Show until" className={`${input} mt-1 block`} value={expires} onChange={(e) => setExpires(e.target.value)} />
        </label>
        <div className="ml-auto flex gap-2">
          <Button onClick={onClose} disabled={busy}>Cancel</Button>
          <Button onClick={send} disabled={busy || !title.trim()}>
            {busy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} aria-hidden />} Post notice
          </Button>
        </div>
      </div>
      <FormError message={error} />
    </div>
  );
}
