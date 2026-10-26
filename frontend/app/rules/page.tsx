"use client";

import clsx from "clsx";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { FormError } from "@/components/Field";
import { Badge, Button, Card, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTimetable } from "@/lib/timetable-context";
import type { Rule } from "@/lib/types";

const input = "rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";

function describe(r: Rule): string {
  const who = r.years.length ? `Year ${r.years.join(", ")}` : "All years";
  if (r.kind === "max_per_day") return `${who}: at most ${r.max_periods ?? "?"} periods a day`;
  if (r.kind === "spread_lunch") return `${who}: lunch spread evenly over the mess window (e.g. half the students at the first lunch period, half at the next), so the mess is never crowded`;
  const days = r.days.length ? r.days.join(", ") : "every day";
  const when = r.after && r.before ? `between ${r.after} and ${r.before}` : r.after ? `after ${r.after}` : r.before ? `before ${r.before}` : "all day";
  return `${who}: no classes ${when} on ${days}`;
}

export default function RulesPage() {
  const { role, member } = useAuth();
  const { college, reload } = useTimetable();
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.rules().then(setRules).catch((e) => setError(e instanceof Error ? e.message : "Couldn't load rules"));
  }, []);
  if (!rules || !college) return <Skeleton className="mx-auto h-64 max-w-4xl" />;

  const mine = (r: Rule) => role === "admin" || (role === "coordinator" && r.department_id === member?.department_id);
  const dept = new Map(college.departments.map((d) => [d.id, d.short]));
  const update = (id: string, patch: Partial<Rule>) => {
    setSaved(false);
    setRules(rules.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  };
  const add = (kind: Rule["kind"]) => {
    setSaved(false);
    setRules([...rules, {
      id: `r-${Date.now()}`,
      name: kind === "no_classes" ? "No classes late on Friday" : kind === "spread_lunch" ? "Spread lunch evenly" : "Not too many periods a day",
      kind, mode: kind === "spread_lunch" ? "try" : "must", weight: 5, enabled: true,
      department_id: role === "coordinator" ? member?.department_id ?? null : null, years: [],
      days: kind === "no_classes" ? ["Fri"] : [], after: kind === "no_classes" ? "15:00" : null, before: null,
      max_periods: kind === "max_per_day" ? 6 : null,
    }]);
  };
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.saveRules(rules);
      await reload();
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Rules" subtitle="Must = never broken. Try = a preference the timetable follows when it can. Changes apply when the timetable is next generated."
        actions={<Button variant="primary" onClick={save} disabled={busy}>{busy && <Loader2 size={16} className="animate-spin" />} Save rules</Button>} />
      <FormError message={error} />
      {saved && <p className="mb-3 text-sm text-ok">Saved. Regenerate the timetable to apply them.</p>}
      <div className="space-y-3">
        {rules.length === 0 && <Card className="p-6 text-center text-sm text-muted">No rules yet. The timetable already avoids clashes, gaps and overloads; add rules for your college&apos;s own needs.</Card>}
        {rules.map((r) => {
          const editable = mine(r);
          return (
            <Card key={r.id} className={clsx("p-4", !r.enabled && "opacity-60")}>
              <div className="flex flex-wrap items-center gap-2">
                <input className={`${input} min-w-0 flex-1 font-medium`} value={r.name} disabled={!editable} aria-label="Rule name"
                  onChange={(e) => update(r.id, { name: e.target.value })} />
                <Badge tone={r.department_id ? "neutral" : "accent"}>{r.department_id ? dept.get(r.department_id) : "Whole college"}</Badge>
                <div className="inline-flex rounded-lg border border-border p-0.5">
                  {(r.kind === "spread_lunch" ? (["try"] as const) : (["must", "try"] as const)).map((m) => (
                    <button key={m} disabled={!editable} aria-pressed={r.mode === m} onClick={() => update(r.id, { mode: m })}
                      className={clsx("rounded-md px-2.5 py-1 text-xs", r.mode === m ? "bg-accent-soft font-medium text-accent-text" : "text-muted")}>
                      {m === "must" ? "Must" : "Try"}
                    </button>
                  ))}
                </div>
                <label className="flex items-center gap-1 text-xs text-muted">
                  <input type="checkbox" checked={r.enabled} disabled={!editable} onChange={(e) => update(r.id, { enabled: e.target.checked })} /> On
                </label>
                {editable && (
                  <button aria-label="Delete rule" onClick={() => setRules(rules.filter((x) => x.id !== r.id))}
                    className="rounded p-1.5 text-muted hover:bg-surface-2"><Trash2 size={14} /></button>
                )}
              </div>
              <p className="mt-2 text-sm text-muted">{describe(r)}</p>
              {editable && (
                <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                  {role === "admin" && (
                    <select className={input} value={r.department_id ?? ""} aria-label="Applies to"
                      onChange={(e) => update(r.id, { department_id: e.target.value || null })}>
                      <option value="">Whole college</option>
                      {college.departments.map((d) => <option key={d.id} value={d.id}>{d.short}</option>)}
                    </select>
                  )}
                  <span className="flex items-center gap-1">Years
                    {[...new Set(college.sections.map((s) => s.year))].sort().map((y) => (
                      <label key={y} className="flex items-center gap-0.5"><input type="checkbox" checked={r.years.includes(y)}
                        onChange={(e) => update(r.id, { years: e.target.checked ? [...r.years, y] : r.years.filter((x) => x !== y) })} />{y}</label>
                    ))}
                    <span className="text-xs text-muted">(none = all)</span>
                  </span>
                  {r.kind === "no_classes" ? (
                    <>
                      <span className="flex items-center gap-1">
                        {college.days.map((d) => (
                          <label key={d} className="flex items-center gap-0.5"><input type="checkbox" checked={r.days.includes(d)}
                            onChange={(e) => update(r.id, { days: e.target.checked ? [...r.days, d] : r.days.filter((x) => x !== d) })} />{d}</label>
                        ))}
                      </span>
                      <label className="flex items-center gap-1">after <input type="time" className={input} value={r.after ?? ""}
                        onChange={(e) => update(r.id, { after: e.target.value || null })} /></label>
                      <label className="flex items-center gap-1">before <input type="time" className={input} value={r.before ?? ""}
                        onChange={(e) => update(r.id, { before: e.target.value || null })} /></label>
                    </>
                  ) : r.kind === "spread_lunch" ? null : (
                    <label className="flex items-center gap-1">at most <input type="number" min={1} max={12} className={`${input} w-16`}
                      value={r.max_periods ?? ""} onChange={(e) => update(r.id, { max_periods: Number(e.target.value) || null })} /> periods a day</label>
                  )}
                  {r.mode === "try" && (
                    <label className="flex items-center gap-1">importance <input type="range" min={1} max={10} value={r.weight}
                      onChange={(e) => update(r.id, { weight: Number(e.target.value) })} /> {r.weight}</label>
                  )}
                </div>
              )}
            </Card>
          );
        })}
      </div>
      {(role === "admin" || role === "coordinator") && (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={() => add("no_classes")}><Plus size={16} /> No classes at certain times</Button>
          <Button onClick={() => add("max_per_day")}><Plus size={16} /> Max periods a day</Button>
          {!rules.some((r) => r.kind === "spread_lunch" && r.department_id === (role === "coordinator" ? member?.department_id ?? null : null)) && (
            <Button onClick={() => add("spread_lunch")}><Plus size={16} /> Spread lunch evenly (mess split)</Button>
          )}
        </div>
      )}
    </div>
  );
}
