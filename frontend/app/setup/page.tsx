"use client";

import clsx from "clsx";
import { Check, ChevronLeft, ChevronRight, Loader2, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { planToShift, type ShiftPlan, ShiftEditor, shiftToPlan } from "@/components/setup/ShiftEditor";
import { Button, Card, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTimetable } from "@/lib/timetable-context";
import type { Department, Holiday, Settings, Venue } from "@/lib/types";
import { usePagePrompts } from "@/lib/chat-context";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const STEPS = ["Week & labs", "Timings", "Calendar", "Departments & rooms", "Sections → shifts", "Done"];
const SECTION_SHIFTS = 4; // only shown when the college runs two shifts
// Links (e.g. from the setup checklist) open a step: /setup?step=timings
const STEP_KEYS = ["week", "timings", "calendar", "departments", "sections", "done"];
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "x";
const input = "rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";

export default function SetupPage() {
  const { role } = useAuth();
  const { college, reload } = useTimetable();
  const [step, setStep] = useState(0);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [plans, setPlans] = useState<ShiftPlan[]>([]);
  const [depts, setDepts] = useState<Department[]>([]);
  const [rooms, setRooms] = useState<Venue[]>([]);
  const [sectionShift, setSectionShift] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  usePagePrompts(["What's still missing before I can generate?", "Which departments aren't Ready yet?",
    "How does the lunch window work?"]);

  useEffect(() => {
    api.settings().then((s) => {
      setSettings(s);
      setPlans(s.shifts.map(shiftToPlan));
    }).catch((e) => setError(e instanceof Error ? e.message : "Couldn't load settings"));
  }, []);
  useEffect(() => {
    const at = STEP_KEYS.indexOf(new URLSearchParams(window.location.search).get("step") ?? "");
    if (at >= 0) setStep(at);
  }, []);
  useEffect(() => {
    if (!college) return;
    setDepts(college.departments);
    setRooms(college.venues.filter((v) => !v.department_id));
    setSectionShift(Object.fromEntries(college.sections.map((s) => [s.id, s.shift_id])));
  }, [college]);

  if (role !== "admin") {
    return <Card className="mx-auto max-w-xl p-6 text-sm">Only the College Admin can run the college setup.</Card>;
  }
  if (!settings || !college) return <Skeleton className="mx-auto h-96 max-w-4xl" />;

  const save = async (): Promise<boolean> => {
    setBusy(true);
    setError(null);
    try {
      let out;
      if (step <= 2) {
        out = await api.saveSettings({ ...settings, shifts: plans.map(planToShift) });
      } else if (step === 3) {
        out = await api.saveDepartments(depts, rooms);
      } else if (step === 4) {
        out = await api.saveSectionShifts(sectionShift);
      }
      if (out) setProblems(out.problems);
      await reload();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save");
      return false;
    } finally {
      setBusy(false);
    }
  };
  const twoShifts = plans.length > 1;
  // A one-shift college never sees the "which sections in which shift" step.
  const visibleSteps = STEPS.map((label, i) => ({ label, i })).filter((s) => twoShifts || s.i !== SECTION_SHIFTS);
  const move = (dir: 1 | -1) => {
    let to = step + dir;
    if (to === SECTION_SHIFTS && !twoShifts) to += dir;
    return Math.min(STEPS.length - 1, Math.max(0, to));
  };
  const next = async () => {
    if (step < STEPS.length - 1 && (await save())) setStep(move(1));
  };
  // Jumping to another step saves this one first, so nothing typed is lost.
  const jump = async (to: number) => {
    if (to === step) return;
    if (step === STEPS.length - 1 || (await save())) setStep(to);
  };
  // Which step a save error belongs to, from what it talks about.
  const errorStep = !error ? null
    : /shift|period|mess window|lunch|break/i.test(error) ? 1
      : /working day|lab must/i.test(error) ? 0
        : /holiday|semester/i.test(error) ? 2
          : /department|room/i.test(error) ? 3 : null;
  // A tick means the answers are saved, not just that the step was passed.
  const saved = (i: number) =>
    i <= 2 ? college.setup_saved !== false
      : i === 3 ? college.departments.length > 0
        : i === SECTION_SHIFTS ? college.sections.length > 0 : false;

  const setShiftCount = (n: number) => {
    if (n === 1) setPlans(plans.slice(0, 1));
    else if (plans.length < 2)
      setPlans([
        { ...plans[0], id: plans[0]?.id ?? "morning", name: plans[0]?.name ?? "Morning" },
        // Back-to-back periods with a flexible lunch, like the first shift: every section gets one free period
        // inside the window each day.
        { id: "evening", name: "Evening", start: "12:00", minutes: plans[0]?.minutes ?? 50, count: 7,
          breaks: [], lunch: true, lunchFrom: "12:50", lunchTo: "15:20" },
      ]);
  };

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="College setup" subtitle="A few questions about how your college runs. You can come back and change any answer." />

      <ol className="mb-6 flex flex-wrap gap-2" aria-label="Setup steps">
        {visibleSteps.map(({ label, i }, n) => (
          <li key={label}>
            <button onClick={() => jump(i)} disabled={busy}
              className={clsx("flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition",
                i === step ? "border-accent bg-accent-soft font-medium text-accent-text"
                  : saved(i) ? "border-border text-text" : "border-border text-muted")}
              aria-current={i === step ? "step" : undefined}>
              <span className={clsx("grid h-5 w-5 place-items-center rounded-full text-[10px]",
                saved(i) ? "bg-ok text-white dark:text-bg" : "bg-surface-2")}>{saved(i) ? <Check size={12} /> : n + 1}</span>
              {label}
            </button>
          </li>
        ))}
      </ol>

      <Card className="p-6">
        {error && (
          // Shown at the top of the step, with a jump to the step the problem belongs to.
          <div role="alert" className="mb-4 flex flex-wrap items-center gap-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
            <span className="min-w-0 flex-1">{error}</span>
            {errorStep !== null && errorStep !== step && (
              <button onClick={() => { setError(null); setStep(errorStep); }} className="font-medium underline">
                Go to {STEPS[errorStep]}
              </button>
            )}
          </div>
        )}
        {step === 0 && (
          <div className="space-y-5">
            <div>
              <h2 className="font-semibold">Which days do you teach?</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {WEEKDAYS.map((d) => {
                  const on = settings.days.includes(d);
                  return (
                    <button key={d} aria-pressed={on}
                      onClick={() => setSettings({ ...settings, days: on ? settings.days.filter((x) => x !== d) : [...settings.days, d] })}
                      className={clsx("rounded-lg border px-4 py-2 text-sm", on ? "border-accent bg-accent-soft text-accent-text" : "border-border text-muted")}>
                      {d}
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <h2 className="font-semibold">How long is a lab?</h2>
              <p className="text-sm text-muted">One lab length for the whole college, in back-to-back periods.</p>
              <div className="mt-2 flex items-center gap-2 text-sm">
                <input type="number" min={1} max={4} className={`${input} w-20`} value={settings.lab_periods}
                  onChange={(e) => setSettings({ ...settings, lab_periods: Math.max(1, Number(e.target.value) || 1) })} />
                periods
              </div>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <div>
              <h2 className="font-semibold">Does your college run one batch of timings, or two shifts?</h2>
              <div className="mt-3 flex gap-2">
                {[1, 2].map((n) => (
                  <button key={n} aria-pressed={plans.length === n} onClick={() => setShiftCount(n)}
                    className={clsx("rounded-lg border px-4 py-2 text-sm", plans.length === n ? "border-accent bg-accent-soft text-accent-text" : "border-border text-muted")}>
                    {n === 1 ? "One timing for everyone" : "Two shifts (e.g. morning / evening)"}
                  </button>
                ))}
              </div>
              {twoShifts && (
                <p className="mt-2 text-sm text-muted">
                  Every section belongs to exactly one shift (you&apos;ll choose in the next steps). Shifts may overlap in time; rooms
                  and teachers are shared safely between them.
                </p>
              )}
            </div>
            {plans.map((p, i) => (
              <ShiftEditor key={i} plan={p} single={!twoShifts} onChange={(np) => setPlans(plans.map((x, j) => (j === i ? { ...np, id: np.id || slug(np.name) } : x)))} />
            ))}
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h2 className="font-semibold">Semester dates <span className="font-normal text-muted">(tentative, editable later)</span></h2>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <input type="date" className={input} value={settings.semester_start ?? ""}
                  onChange={(e) => setSettings({ ...settings, semester_start: e.target.value || null })} />
                <span className="text-muted">to</span>
                <input type="date" className={input} value={settings.semester_end ?? ""}
                  onChange={(e) => setSettings({ ...settings, semester_end: e.target.value || null })} />
              </div>
            </div>
            <HolidayEditor holidays={settings.holidays} onChange={(h) => setSettings({ ...settings, holidays: h })} />
          </div>
        )}

        {step === 3 && <DepartmentsEditor depts={depts} setDepts={setDepts} rooms={rooms} setRooms={setRooms} />}

        {step === 4 && (
          <div>
            <h2 className="font-semibold">Which sections study in which shift?</h2>
            {!twoShifts ? (
              <p className="mt-2 text-sm text-muted">You run one shift, so every section is in {plans[0]?.name}. Nothing to do here.</p>
            ) : college.sections.length === 0 ? (
              <p className="mt-2 text-sm text-muted">
                No sections yet. Department Coordinators add them (Shift column in their Excel sheet); you can come back here
                to change shifts for many sections at once.
              </p>
            ) : (
              <>
                <p className="mt-1 text-sm text-muted">Quick choice by year, then adjust single sections (e.g. day-scholar sections in the morning).</p>
                <div className="mt-3 flex flex-wrap gap-2 text-sm">
                  {[...new Set(college.sections.map((s) => s.year))].sort().map((y) => (
                    <span key={y} className="flex items-center gap-1 rounded-lg border border-border px-2 py-1">
                      Year {y}:
                      {plans.map((p) => (
                        <button key={p.id} onClick={() => setSectionShift({ ...sectionShift, ...Object.fromEntries(
                          college.sections.filter((s) => s.year === y).map((s) => [s.id, p.id])) })}
                          className="rounded px-2 py-0.5 text-accent-text hover:bg-accent-soft">{p.name}</button>
                      ))}
                    </span>
                  ))}
                </div>
                <div className="mt-4 max-h-80 overflow-auto rounded-lg border border-border">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-surface-2 text-left text-xs text-muted">
                      <tr><th className="px-3 py-2">Section</th><th className="px-3 py-2">Year</th><th className="px-3 py-2">Students</th><th className="px-3 py-2">Shift</th></tr>
                    </thead>
                    <tbody>
                      {college.sections.map((s) => (
                        <tr key={s.id} className="border-t border-border">
                          <td className="px-3 py-1.5 font-medium">{s.name}</td>
                          <td className="px-3 py-1.5">{s.year}</td>
                          <td className="px-3 py-1.5">{s.strength}</td>
                          <td className="px-3 py-1.5">
                            <select className={input} value={sectionShift[s.id]} aria-label={`Shift for ${s.name}`}
                              onChange={(e) => setSectionShift({ ...sectionShift, [s.id]: e.target.value })}>
                              {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                            </select>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {step === 5 && (
          <div>
            <h2 className="font-semibold">College settings saved</h2>
            <p className="mt-1 text-sm text-muted">Next, each Department Coordinator downloads their department&rsquo;s Excel sheet, fills it in, uploads it, checks the teacher suggestions and marks it Ready.</p>
            <ul className="mt-4 space-y-2 text-sm">
              <li><Link href="/members" className="text-accent-text hover:underline">Invite Department Coordinators →</Link></li>
              {college.departments.map((d) => (
                <li key={d.id}><Link href={`/departments/${d.id}`} className="text-accent-text hover:underline">Open {d.name} →</Link></li>
              ))}
              <li><Link href="/" className="text-accent-text hover:underline">Back to the dashboard →</Link></li>
            </ul>
            {problems.length > 0 && (
              <div className="mt-4 rounded-lg bg-warn-soft p-3 text-sm text-warn">
                <p className="font-medium">Still needed before generating:</p>
                <ul className="mt-1 list-disc pl-5">{problems.slice(0, 6).map((p) => <li key={p}>{p}</li>)}</ul>
              </div>
            )}
          </div>
        )}

        {step < STEPS.length - 1 && (
          <div className="mt-6 flex justify-between border-t border-border pt-4">
            <Button onClick={() => setStep(move(-1))} disabled={step === 0 || busy}>
              <ChevronLeft size={16} /> Back
            </Button>
            <Button variant="primary" onClick={next} disabled={busy}>
              {busy && <Loader2 size={16} className="animate-spin" />} Save & continue <ChevronRight size={16} />
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}

function HolidayEditor({ holidays, onChange }: { holidays: Holiday[]; onChange: (h: Holiday[]) => void }) {
  const [paste, setPaste] = useState("");
  const addPasted = () => {
    // One per line: 2026-11-08, Diwali   (also accepts 08/11/2026 Diwali)
    const rows = paste.split("\n").map((l) => l.trim()).filter(Boolean).flatMap((l) => {
      const m = l.match(/^(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})[,\s;]+(.+)$/);
      if (!m) return [];
      let date = m[1];
      if (!/^\d{4}/.test(date)) {
        const [d, mo, y] = date.split(/[/-]/);
        date = `${y}-${mo.padStart(2, "0")}-${d.padStart(2, "0")}`;
      }
      return [{ date, label: m[2].trim() }];
    });
    onChange([...holidays, ...rows]);
    setPaste("");
  };
  return (
    <div>
      <h2 className="font-semibold">Holidays</h2>
      <p className="text-sm text-muted">No classes are shown on holidays. Paste your list (one per line: date, name) or add rows.</p>
      <div className="mt-2 space-y-2">
        {holidays.map((h, i) => (
          <div key={i} className="flex items-center gap-2">
            <input type="date" className={input} value={h.date}
              onChange={(e) => onChange(holidays.map((x, j) => (j === i ? { ...x, date: e.target.value } : x)))} />
            <input className={`${input} flex-1`} value={h.label} aria-label="Holiday name"
              onChange={(e) => onChange(holidays.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} />
            <button aria-label="Remove holiday" onClick={() => onChange(holidays.filter((_, j) => j !== i))}
              className="rounded p-1 text-muted hover:bg-surface-2"><Trash2 size={14} /></button>
          </div>
        ))}
        <button onClick={() => onChange([...holidays, { date: "", label: "" }])}
          className="inline-flex items-center gap-1 text-sm text-accent-text hover:underline"><Plus size={14} /> Add a holiday</button>
      </div>
      <textarea value={paste} onChange={(e) => setPaste(e.target.value)} rows={3}
        placeholder={"2026-11-08, Diwali\n15/08/2026 Independence Day"}
        className={`${input} mt-3 w-full font-mono text-xs`} aria-label="Paste holidays" />
      <Button className="mt-2" onClick={addPasted} disabled={!paste.trim()}>Add pasted holidays</Button>
    </div>
  );
}

function DepartmentsEditor({ depts, setDepts, rooms, setRooms }: {
  depts: Department[]; setDepts: (d: Department[]) => void; rooms: Venue[]; setRooms: (v: Venue[]) => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-semibold">Departments</h2>
        <p className="text-sm text-muted">Each department gets a Coordinator who fills in its sections, teachers and subjects.</p>
        <div className="mt-2 space-y-2">
          {depts.map((d, i) => (
            <div key={i} className="flex items-center gap-2">
              <input className={`${input} flex-1`} value={d.name} placeholder="Computer Science & Engineering" aria-label="Department name"
                onChange={(e) => setDepts(depts.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
              <input className={`${input} w-24`} value={d.short} placeholder="CSE" aria-label="Short name"
                onChange={(e) => setDepts(depts.map((x, j) => (j === i ? { ...x, short: e.target.value, id: x.id || slug(e.target.value) } : x)))} />
              <button aria-label="Remove department" onClick={() => setDepts(depts.filter((_, j) => j !== i))}
                className="rounded p-1 text-muted hover:bg-surface-2"><Trash2 size={14} /></button>
            </div>
          ))}
          <button onClick={() => setDepts([...depts, { id: "", name: "", short: "" }])}
            className="inline-flex items-center gap-1 text-sm text-accent-text hover:underline"><Plus size={14} /> Add a department</button>
        </div>
      </div>
      <div>
        <h2 className="font-semibold">Shared rooms</h2>
        <p className="text-sm text-muted">Seminar halls, big lecture theatres, common labs. Department rooms are added by each department.</p>
        <div className="mt-2 space-y-2">
          {rooms.map((v, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2">
              <input className={`${input} flex-1`} value={v.name} placeholder="Seminar Hall" aria-label="Room name"
                onChange={(e) => setRooms(rooms.map((x, j) => (j === i ? { ...x, name: e.target.value, id: x.id || slug(e.target.value) } : x)))} />
              <select className={input} value={v.type} aria-label="Room type"
                onChange={(e) => setRooms(rooms.map((x, j) => (j === i ? { ...x, type: e.target.value as Venue["type"] } : x)))}>
                <option value="lecture">Lecture</option><option value="seminar">Seminar</option><option value="lab">Lab</option>
              </select>
              <input type="number" min={1} className={`${input} w-24`} value={v.capacity} aria-label="Seats"
                onChange={(e) => setRooms(rooms.map((x, j) => (j === i ? { ...x, capacity: Number(e.target.value) } : x)))} />
              <input className={`${input} w-40`} value={v.tags.join(", ")} placeholder="equipment (labs)" aria-label="Equipment"
                onChange={(e) => setRooms(rooms.map((x, j) => (j === i ? { ...x, tags: e.target.value.split(",").map((t) => t.trim()).filter(Boolean) } : x)))} />
              <button aria-label="Remove room" onClick={() => setRooms(rooms.filter((_, j) => j !== i))}
                className="rounded p-1 text-muted hover:bg-surface-2"><Trash2 size={14} /></button>
            </div>
          ))}
          <button onClick={() => setRooms([...rooms, { id: "", name: "", type: "seminar", capacity: 120, tags: [], department_id: null }])}
            className="inline-flex items-center gap-1 text-sm text-accent-text hover:underline"><Plus size={14} /> Add a shared room</button>
        </div>
      </div>
    </div>
  );
}
