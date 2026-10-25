"use client";

import { AlertTriangle, CheckCircle2, ChevronDown, Download, Loader2, Shuffle, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button, Card } from "@/components/ui";
import { api } from "@/lib/api";
import { useTimetable } from "@/lib/timetable-context";
import type { SectioningOptions, SectioningOut } from "@/lib/types";

const input = "rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";

/** Split a whole-year student list into balanced sections + lab batches. Preview first, then save. */
export function AutoSectionCard({ dept, onSaved }: { dept: string; onSaved: () => Promise<void> }) {
  const { college } = useTimetable();
  const fileRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [opts, setOpts] = useState<SectioningOptions>({ year: 1, max_size: 60, batches: 2 });
  const [out, setOut] = useState<SectioningOut | null>(null);
  const [busy, setBusy] = useState<"" | "check" | "save" | "download">("");
  const [error, setError] = useState<string | null>(null);

  const short = college?.departments.find((d) => d.id === dept)?.short ?? dept.toUpperCase();
  const shifts = college?.shifts ?? [];

  // Re-check the preview whenever the file or an option changes (nothing is saved).
  useEffect(() => {
    if (!file) return;
    let live = true;
    setBusy("check");
    setError(null);
    api.autoSections(dept, file, opts, false)
      .then((r) => { if (live) setOut(r); })
      .catch((e) => { if (live) setError(e instanceof Error ? e.message : "Couldn't read the file"); })
      .finally(() => { if (live) setBusy(""); });
    return () => { live = false; };
  }, [dept, file, opts]);

  const save = async () => {
    if (!file) return;
    setBusy("save");
    setError(null);
    try {
      setOut(await api.autoSections(dept, file, opts, true));
      await onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save");
    } finally {
      setBusy("");
    }
  };

  const set = (patch: Partial<SectioningOptions>) => setOpts((o) => ({ ...o, ...patch }));
  const plan = out?.plan;

  return (
    <Card className="p-5">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center gap-2 text-left">
        <Shuffle size={16} aria-hidden />
        <span className="flex-1">
          <span className="block text-sm font-semibold">Make sections from a whole-year list</span>
          <span className="block text-xs text-muted">Got one list of every student in a year? Split it into sections and lab batches automatically.</span>
        </span>
        <ChevronDown size={16} className={open ? "rotate-180 transition" : "transition"} aria-hidden />
      </button>

      {open && (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button onClick={async () => { setBusy("download"); try { await api.downloadYearTemplate(dept); } finally { setBusy(""); } }}
              disabled={!!busy}>
              {busy === "download" ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} Year list template
            </Button>
            <Button onClick={() => fileRef.current?.click()} disabled={busy === "save"}>
              <Upload size={16} /> {file ? "Choose another list" : "Upload year list"}
            </Button>
            <input ref={fileRef} type="file" accept=".xlsx" className="hidden" aria-label="Upload year list"
              onChange={(e) => { setOut(null); setFile(e.target.files?.[0] ?? null); }} />
          </div>

          <div className="flex flex-wrap items-end gap-2">
            <label className="text-xs text-muted">Year
              <select aria-label="Year" className={`${input} mt-1 block`} value={opts.year}
                onChange={(e) => set({ year: Number(e.target.value) })}>
                {[1, 2, 3, 4, 5].map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </label>
            <label className="text-xs text-muted">Max students per section
              <input aria-label="Max students per section" type="number" min={5} max={300} className={`${input} mt-1 block w-28`}
                value={opts.max_size} onChange={(e) => set({ max_size: Math.max(5, Math.min(300, Number(e.target.value) || 60)) })} />
            </label>
            <label className="text-xs text-muted">Lab batches per section
              <select aria-label="Lab batches per section" className={`${input} mt-1 block`} value={opts.batches}
                onChange={(e) => set({ batches: Number(e.target.value) })}>
                {[1, 2, 3, 4].map((b) => <option key={b} value={b}>{b === 1 ? "None (whole section)" : b}</option>)}
              </select>
            </label>
            {shifts.length > 1 && (
              <label className="text-xs text-muted">Shift
                <select aria-label="Shift" className={`${input} mt-1 block`} value={opts.shift_id ?? ""}
                  onChange={(e) => set({ shift_id: e.target.value || undefined })}>
                  <option value="">Same as now</option>
                  {shifts.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </label>
            )}
            <label className="text-xs text-muted">How to split
              <select aria-label="How to split" className={`${input} mt-1 block`} value={opts.mix_by ?? ""}
                onChange={(e) => set({ mix_by: e.target.value || undefined })}>
                <option value="">By roll number</option>
                {(out?.columns ?? []).map((c) => <option key={c} value={c}>Mix evenly by {c}</option>)}
              </select>
            </label>
            <label className="text-xs text-muted">Names
              <input aria-label="Section name prefix" className={`${input} mt-1 block w-28`} placeholder={`${short}-${opts.year}`}
                value={opts.prefix ?? ""} maxLength={20} onChange={(e) => set({ prefix: e.target.value || undefined })} />
            </label>
          </div>

          {error && <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
          {busy === "check" && <p className="flex items-center gap-2 text-sm text-muted"><Loader2 size={14} className="animate-spin" /> Splitting the list…</p>}
          {!file && <p className="text-sm text-muted">Upload the list to see the sections before anything is saved.</p>}

          {out && out.errors.length > 0 && (
            <div>
              <p className="text-sm font-medium text-danger">{out.errors.length} row(s) need fixing. Nothing was saved.</p>
              <ul className="mt-2 max-h-48 space-y-1 overflow-auto text-sm">
                {out.errors.map((e, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="shrink-0 rounded bg-danger-soft px-1.5 font-mono text-xs text-danger">{e.row ? `Row ${e.row}` : "File"}</span>
                    <span>{e.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {plan && (
            <div className="rounded-lg border border-border">
              <div className="border-b border-border px-4 py-2.5 text-sm">
                <b>{plan.students}</b> students → <b>{plan.sections.length}</b> section{plan.sections.length === 1 ? "" : "s"}
                {plan.replaces.length > 0 && (
                  <span className="block text-xs text-muted">
                    Replaces year {plan.year}&rsquo;s current sections ({plan.replaces.join(", ")}). Sections with the same name
                    keep their classes; students keep their accounts.
                  </span>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-xs text-muted">
                    <tr><th className="px-4 py-2 font-medium">Section</th><th className="px-2 py-2 font-medium">Students</th>
                      <th className="px-2 py-2 font-medium">Lab batches</th><th className="px-2 py-2 font-medium">Roll numbers</th>
                      {opts.mix_by && <th className="px-2 py-2 font-medium">{opts.mix_by}</th>}</tr>
                  </thead>
                  <tbody>
                    {plan.sections.map((s) => (
                      <tr key={s.name} className="border-t border-border">
                        <td className="px-4 py-2 font-medium">{s.name}</td>
                        <td className="px-2 py-2">{s.size}</td>
                        <td className="px-2 py-2 text-muted">{s.batches.length ? s.batches.map((b, i) => `B${i + 1}: ${b}`).join(" · ") : "—"}</td>
                        <td className="whitespace-nowrap px-2 py-2 text-muted">{s.first_roll} – {s.last_roll}</td>
                        {opts.mix_by && <td className="px-2 py-2 text-muted">{Object.entries(s.mix).map(([k, v]) => `${k}: ${v}`).join(" · ")}</td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {(plan.warnings.length > 0 || out.problems.length > 0) && (
                <ul className="space-y-1 border-t border-border px-4 py-3 text-sm">
                  {out.problems.map((p) => <li key={p} className="flex gap-2 text-danger"><AlertTriangle size={15} className="mt-0.5 shrink-0" aria-hidden />{p}</li>)}
                  {plan.warnings.map((w) => <li key={w} className="flex gap-2 text-warn"><AlertTriangle size={15} className="mt-0.5 shrink-0" aria-hidden />{w}</li>)}
                </ul>
              )}
              <div className="border-t border-border px-4 py-3">
                {out.saved ? (
                  <p className="flex items-center gap-2 text-sm text-ok"><CheckCircle2 size={16} aria-hidden /> Saved. Next, add this year&rsquo;s classes (Excel sheet, Classes tab) and mark the department Ready again.</p>
                ) : (
                  <Button variant="primary" onClick={save} disabled={!!busy || out.problems.length > 0}>
                    {busy === "save" && <Loader2 size={16} className="animate-spin" />} Save {plan.sections.length} section{plan.sections.length === 1 ? "" : "s"}
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
