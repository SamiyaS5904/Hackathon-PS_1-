"use client";

import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Download, FileSpreadsheet, Loader2, Sparkles, Upload } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AutoSectionCard } from "@/components/departments/AutoSectionCard";
import { Badge, Button, Card, ErrorCard, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTimetable } from "@/lib/timetable-context";
import type { DepartmentReadiness, DeptData, ImportOut, Suggestion } from "@/lib/types";
import { usePagePrompts } from "@/lib/chat-context";

const COUNT_LABEL: Record<string, string> = {
  sections: "sections", teachers: "teachers", subjects: "subjects", can_teach: "'can teach' entries",
  classes: "classes", students: "students", rooms: "rooms",
};

export default function DepartmentPage() {
  const { dept } = useParams<{ dept: string }>();
  const { role, member } = useAuth();
  const { college, reload } = useTimetable();
  const [data, setData] = useState<DeptData | null>(null);
  const [status, setStatus] = useState<DepartmentReadiness | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const deptName = college?.departments.find((d) => d.id === dept)?.short ?? "this department";
  const firstSection = college?.sections.find((s) => s.department_id === dept)?.name;
  usePagePrompts([`What's missing in ${deptName} before it can be marked Ready?`, "Which teachers have the most periods?",
    firstSection ? `Who is below 75% attendance in ${firstSection}?` : "Which classes still need a teacher?"]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [d, r, pre] = await Promise.all([api.deptData(dept), api.readiness(), api.precheck()]);
      setData(d);
      setStatus(r.find((x) => x.department_id === dept) ?? null);
      // Only what this department can fix here.
      setProblems((pre.located ?? []).filter((p) => p.link === `/departments/${dept}`).map((p) => p.message));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load the department");
    }
  }, [dept]);
  useEffect(() => {
    load();
  }, [load]);

  const name = college?.departments.find((d) => d.id === dept)?.name ?? dept;
  const allowed = role === "admin" || (role === "coordinator" && member?.department_id === dept);
  if (!allowed) return <Card className="mx-auto max-w-xl p-6 text-sm">Only this department&apos;s Coordinator or the College Admin can open it.</Card>;

  const refresh = async () => {
    await Promise.all([load(), reload()]);
  };

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title={name} subtitle="Sections, teachers, subjects and classes for this department."
        actions={status && <ReadyButton dept={dept} status={status} onDone={refresh} setError={setError} />} />
      {error && <ErrorCard message={error} onRetry={() => { setError(null); load(); }} />}
      {!data || !college ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <div className="space-y-4">
          {status && (
            <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
              {([["Sections", status.sections], ["Teachers", status.teachers], ["Subjects", status.subjects],
                ["Classes", status.classes], ["Without teacher", status.without_teacher], ["Students", status.students]] as const)
                .map(([k, v]) => (
                  <div key={k} className={clsx("rounded-xl border bg-surface px-3 py-2",
                    k === "Without teacher" && v > 0 ? "border-warn/40" : "border-border")}>
                    <p className="text-xs text-muted">{k}</p>
                    <p className="text-lg font-semibold">{v}</p>
                  </div>
                ))}
            </div>
          )}
          <ExcelCard dept={dept} onSaved={refresh} />
          <AutoSectionCard dept={dept} onSaved={refresh} />
          <ClassesCard dept={dept} data={data} onSaved={refresh} />
          {problems.length > 0 && (
            <Card className="p-5">
              <h2 className="flex items-center gap-2 text-sm font-semibold"><AlertTriangle size={16} className="text-warn" /> Still to fix in this department before the timetable can be generated</h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">{problems.slice(0, 8).map((p) => <li key={p}>{p}</li>)}</ul>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

function ReadyButton({ dept, status, onDone, setError }: {
  dept: string; status: DepartmentReadiness; onDone: () => Promise<void>; setError: (e: string | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.ready(dept, !status.ready);
      await onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't update");
    } finally {
      setBusy(false);
    }
  };
  return status.ready ? (
    <div className="flex items-center gap-2">
      <Badge tone="ok"><CheckCircle2 size={12} /> Ready{status.by ? ` · ${status.by}` : ""}</Badge>
      <Button variant="ghost" onClick={toggle} disabled={busy}>Mark not ready</Button>
    </div>
  ) : (
    // Only offered once there is something to be Ready with; otherwise say what's missing.
    (() => {
      const missing = !status.sections ? "Add sections first (Excel sheet)"
        : !status.classes ? "Add classes first (Excel sheet, Classes tab)"
          : status.without_teacher ? `${status.without_teacher} class(es) still need a teacher` : "";
      return (
        <div className="flex flex-col items-end gap-1">
          <Button variant={missing ? "secondary" : "primary"} onClick={toggle} disabled={busy || !!missing}>
            {busy ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />} Mark department Ready
          </Button>
          {missing && <span className="text-xs text-muted">{missing}</span>}
        </div>
      );
    })()
  );
}

function ExcelCard({ dept, onSaved }: { dept: string; onSaved: () => Promise<void> }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportOut | null>(null);
  const [busy, setBusy] = useState<"" | "download" | "check" | "save">("");
  const [error, setError] = useState<string | null>(null);

  const run = async (kind: "download" | "check" | "save", fn: () => Promise<void>) => {
    setBusy(kind);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy("");
    }
  };
  const pick = (f: File | null) => {
    setFile(f);
    setPreview(null);
    if (f) run("check", async () => setPreview(await api.importExcel(dept, f, false)));
  };

  return (
    <Card className="p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold"><FileSpreadsheet size={16} /> Excel</h2>
      <p className="mt-1 text-sm text-muted">
        Download the sheet (already filled with this department&apos;s data), edit it in Excel, and upload it back. Nothing
        is saved until you&apos;ve seen the preview.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button onClick={() => run("download", () => api.downloadTemplate(dept))} disabled={!!busy}>
          {busy === "download" ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} Download sheet
        </Button>
        <Button onClick={() => fileRef.current?.click()} disabled={!!busy}>
          <Upload size={16} /> Upload filled sheet
        </Button>
        <input ref={fileRef} type="file" accept=".xlsx" className="hidden" aria-label="Upload Excel file"
          onChange={(e) => pick(e.target.files?.[0] ?? null)} />
      </div>
      {error && <p className="mt-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {busy === "check" && <p className="mt-3 flex items-center gap-2 text-sm text-muted"><Loader2 size={14} className="animate-spin" /> Checking every row…</p>}
      {preview && file && (
        <div className="mt-4 rounded-lg border border-border p-4">
          <p className="text-sm font-medium">{file.name}</p>
          <p className="mt-1 text-xs text-muted">
            {Object.entries(preview.counts).map(([k, v]) => `${v} ${COUNT_LABEL[k] ?? k.replaceAll("_", " ")}`).join(" · ")}
          </p>
          {preview.errors.length > 0 ? (
            <div className="mt-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium text-danger">{preview.errors.length} row(s) need fixing. Nothing was saved.</p>
                <Button onClick={() => run("download", () => api.downloadMarked(dept, file))} disabled={!!busy}>
                  <Download size={16} aria-hidden /> Sheet with problems marked
                </Button>
              </div>
              <p className="mt-1 text-xs text-muted">The download highlights each row below in red, with the reason in a note on the row.</p>
              <ul className="mt-2 max-h-60 space-y-1 overflow-auto text-sm">
                {preview.errors.map((e, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="shrink-0 rounded bg-danger-soft px-1.5 font-mono text-xs text-danger">
                      {e.sheet ? `${e.sheet} row ${e.row}` : "File"}
                    </span>
                    <span>{e.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : preview.saved ? (
            <p className="mt-3 flex items-center gap-2 text-sm text-ok"><CheckCircle2 size={16} /> Saved. The department is now marked not Ready until you check it again.</p>
          ) : (
            <div className="mt-3">
              <p className="flex items-center gap-2 text-sm text-ok"><CheckCircle2 size={16} /> Every row looks right.</p>
              {preview.problems.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-xs text-muted">{preview.problems.slice(0, 5).map((p) => <li key={p}>{p}</li>)}</ul>
              )}
              <Button className="mt-3" variant="primary" disabled={!!busy}
                onClick={() => run("save", async () => { setPreview(await api.importExcel(dept, file, true)); await onSaved(); })}>
                {busy === "save" && <Loader2 size={16} className="animate-spin" />} Save this data
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function ClassesCard({ dept, data, onSaved }: { dept: string; data: DeptData; onSaved: () => Promise<void> }) {
  const { college } = useTimetable();
  const [chosen, setChosen] = useState<Record<string, string | null>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [unfilled, setUnfilled] = useState<string[]>([]);
  const [busy, setBusy] = useState<"" | "suggest" | "save">("");
  const [message, setMessage] = useState<{ text: string; tone: "ok" | "danger" } | null>(null);

  useEffect(() => {
    setChosen(Object.fromEntries(data.allotments.map((a) => [a.id, a.teacher_id])));
    setReasons({});
  }, [data]);

  const lookup = useMemo(() => ({
    subject: new Map(college?.subjects.map((s) => [s.id, s]) ?? []),
    section: new Map(college?.sections.map((s) => [s.id, s]) ?? []),
    teacher: new Map(college?.teachers.map((t) => [t.id, t]) ?? []),
  }), [college]);
  const canTeach = useMemo(() => {
    const m = new Map<string, Map<string, number>>();
    for (const ts of college?.teacher_subjects ?? []) {
      if (!m.has(ts.subject_id)) m.set(ts.subject_id, new Map());
      m.get(ts.subject_id)!.set(ts.teacher_id, ts.preference);
    }
    return m;
  }, [college]);

  const changed = data.allotments.some((a) => (chosen[a.id] ?? null) !== a.teacher_id);

  const suggestAll = async (onlyBlank: boolean) => {
    setBusy("suggest");
    setMessage(null);
    try {
      const ids = onlyBlank ? [] : data.allotments.map((a) => a.id);
      const r = await api.suggest(dept, ids);
      const pick: Record<string, string | null> = { ...chosen };
      const why: Record<string, string> = {};
      r.suggestions.forEach((s: Suggestion) => {
        pick[s.allotment_id] = s.teacher_id;
        why[s.allotment_id] = s.reason;
      });
      setChosen(pick);
      setReasons(why);
      setUnfilled(r.unfilled);
      setMessage({ text: r.suggestions.length ? `Suggested ${r.suggestions.filter((s) => s.teacher_id).length} teacher(s). Review, then Save.`
        : "Every class already has a teacher.", tone: "ok" });
    } catch (e) {
      setMessage({ text: e instanceof Error ? e.message : "Couldn't suggest", tone: "danger" });
    } finally {
      setBusy("");
    }
  };

  const save = async () => {
    setBusy("save");
    try {
      const changes = Object.fromEntries(data.allotments.filter((a) => (chosen[a.id] ?? null) !== a.teacher_id)
        .map((a) => [a.id, chosen[a.id] ?? null]));
      await api.assign(dept, changes);
      setReasons({});
      await onSaved();
      setMessage({ text: "Teachers saved.", tone: "ok" });
    } catch (e) {
      setMessage({ text: e instanceof Error ? e.message : "Couldn't save", tone: "danger" });
    } finally {
      setBusy("");
    }
  };

  const periods = (subjectId: string, kind: string) => {
    const s = lookup.subject.get(subjectId);
    return s ? (kind === "lab" ? s.labs_per_week * (college?.lab_periods ?? 2) : s.lectures_per_week) : 0;
  };

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
        <div>
          <h2 className="text-sm font-semibold">Classes & teachers <span className="font-normal text-muted">({data.allotments.length})</span></h2>
          <p className="text-xs text-muted">Suggestions use who can teach what (the Excel &quot;Can teach&quot; sheet), preferences and fair weekly loads.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => suggestAll(true)} disabled={!!busy}>
            {busy === "suggest" ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />} Suggest for empty
          </Button>
          <Button variant="ghost" onClick={() => suggestAll(false)} disabled={!!busy}>Re-suggest all</Button>
          <Button variant="primary" onClick={save} disabled={!changed || !!busy}>
            {busy === "save" && <Loader2 size={16} className="animate-spin" />} Save teachers
          </Button>
        </div>
      </div>
      {message && <p className={clsx("px-5 pt-3 text-sm", message.tone === "ok" ? "text-ok" : "text-danger")}>{message.text}</p>}
      {unfilled.length > 0 && (
        <ul className="mx-5 mt-3 list-disc rounded-lg bg-warn-soft py-2 pl-8 pr-3 text-sm text-warn">{unfilled.map((u) => <li key={u}>{u}</li>)}</ul>
      )}
      {data.allotments.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-muted">No classes yet. Add them in the Excel sheet (Classes tab) and upload it.</p>
      ) : (
        <div className="max-h-[560px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-surface-2 text-left text-xs text-muted">
              <tr>
                <th className="px-5 py-2">Subject</th><th className="px-3 py-2">Section</th><th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Periods/wk</th><th className="px-3 py-2">Teacher</th>
              </tr>
            </thead>
            <tbody>
              {data.allotments.map((a) => {
                const subj = lookup.subject.get(a.subject_id);
                const secs = a.section_ids.map((id) => lookup.section.get(id)?.name).join(" + ");
                const batch = a.batch_id ? lookup.section.get(a.section_ids[0])?.batches.find((b) => b.id === a.batch_id)?.name : "";
                const able = canTeach.get(a.subject_id) ?? new Map<string, number>();
                const teachers = [...(college?.teachers ?? [])].sort((x, y) =>
                  (able.get(x.id) ?? 99) - (able.get(y.id) ?? 99) || x.name.localeCompare(y.name));
                const value = chosen[a.id] ?? "";
                return (
                  <tr key={a.id} className={clsx("border-t border-border", reasons[a.id] && "bg-accent-soft/40")}>
                    <td className="px-5 py-2"><span className="font-medium">{subj?.code}</span> <span className="text-muted">{subj?.name}</span></td>
                    <td className="px-3 py-2">{secs}{batch ? ` · ${batch}` : ""}</td>
                    <td className="px-3 py-2">{a.kind === "lab" ? <Badge>Lab</Badge> : "Lecture"}</td>
                    <td className="px-3 py-2">{periods(a.subject_id, a.kind)}</td>
                    <td className="px-3 py-2">
                      <select value={value} aria-label={`Teacher for ${subj?.name} ${secs}`}
                        onChange={(e) => setChosen({ ...chosen, [a.id]: e.target.value || null })}
                        className={clsx("w-full min-w-48 rounded-lg border bg-surface px-2 py-1.5 text-sm",
                          value ? "border-border-strong" : "border-warn/60")}>
                        <option value="">No teacher yet</option>
                        {teachers.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name}{able.has(t.id) ? ` (choice ${able.get(t.id)})` : ""}
                          </option>
                        ))}
                      </select>
                      {reasons[a.id] && <p className="mt-0.5 text-xs text-accent-text">{reasons[a.id]}</p>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
