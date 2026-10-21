"use client";

import { Loader2, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { FormError } from "@/components/Field";
import { Button, Card, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useTimetable } from "@/lib/timetable-context";
import type { TimeBlock } from "@/lib/types";

const input = "rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";

export default function AvailabilityPage() {
  const { college } = useTimetable();
  const [blocked, setBlocked] = useState<TimeBlock[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    api.myBlocked().then((r) => setBlocked(r.blocked)).catch((e) => setError(e instanceof Error ? e.message : "Couldn't load"));
  }, []);

  const save = async () => {
    if (!blocked) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const r = await api.saveMyBlocked(blocked);
      setBlocked(r.blocked);
      setMessage(r.message);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="My availability" subtitle="Times you can't teach every week (another job, research, travel). They're confirmed instantly if they don't clash with your lectures." />
      {!blocked || !college ? (
        error ? <FormError message={error} /> : <Skeleton className="h-48 w-full" />
      ) : (
        <Card className="p-5">
          <div className="space-y-2">
            {blocked.length === 0 && <p className="text-sm text-muted">No blocked times. You can be scheduled any time in your shift.</p>}
            {blocked.map((b, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <select className={input} value={b.day} aria-label="Day"
                  onChange={(e) => setBlocked(blocked.map((x, j) => (j === i ? { ...x, day: e.target.value } : x)))}>
                  {college.days.map((d) => <option key={d}>{d}</option>)}
                </select>
                <input type="time" className={input} value={b.start} aria-label="From"
                  onChange={(e) => setBlocked(blocked.map((x, j) => (j === i ? { ...x, start: e.target.value } : x)))} />
                <span className="text-muted">to</span>
                <input type="time" className={input} value={b.end} aria-label="To"
                  onChange={(e) => setBlocked(blocked.map((x, j) => (j === i ? { ...x, end: e.target.value } : x)))} />
                <button aria-label="Remove" onClick={() => setBlocked(blocked.filter((_, j) => j !== i))}
                  className="rounded p-1.5 text-muted hover:bg-surface-2"><Trash2 size={14} /></button>
              </div>
            ))}
            <button onClick={() => setBlocked([...blocked, { day: college.days[0], start: "09:00", end: "10:00" }])}
              className="inline-flex items-center gap-1 text-sm text-accent-text hover:underline"><Plus size={14} /> Add a blocked time</button>
          </div>
          <FormError message={error} />
          {message && <p className="mt-3 text-sm text-ok">{message}</p>}
          <Button className="mt-4" variant="primary" onClick={save} disabled={busy}>
            {busy && <Loader2 size={16} className="animate-spin" />} Save
          </Button>
          <p className="mt-3 text-xs text-muted">Need just one day off? Open My timetable → This week and cancel or move that lecture instead.</p>
        </Card>
      )}
    </div>
  );
}
