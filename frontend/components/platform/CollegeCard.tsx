"use client";

import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { useState } from "react";
import { Badge, Card } from "@/components/ui";
import { api } from "@/lib/api";
import type { CollegeSummary } from "@/lib/types";

const STAGE_TONE: Record<string, "ok" | "accent" | "warn" | "neutral"> = {
  Live: "ok", Draft: "accent", "Ready to generate": "accent", "Out of date": "warn",
  "Collecting data": "neutral", "Setting up": "neutral",
};
const STATUS_LABEL = { active: "Active", read_only: "Read-only", paused: "Paused" } as const;
const select = "rounded-md border border-border-strong bg-surface px-2 py-1 text-xs";

export function ago(t: number): string {
  const s = Date.now() / 1000 - t;
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  const d = Math.round(s / 86400);
  return d === 1 ? "yesterday" : `${d} days ago`;
}

/** One college as the platform owner sees it: size, progress, adoption, health; plan / status controls. */
export function CollegeCard({ c, onChange }: { c: CollegeSummary; onChange: (c: CollegeSummary) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState(c.note);

  const save = async (body: { plan?: string; status?: string; note?: string }) => {
    if (body.status === "paused" && !window.confirm(`Pause ${c.name}? Its members won't be able to open it until you reactivate it.`)) return;
    setBusy(true);
    setError(null);
    try {
      onChange(await api.updateCollege(c.id, body));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save");
    } finally {
      setBusy(false);
    }
  };

  const ready = c.departments ? Math.round((100 * c.departments_ready) / c.departments) : 0;
  return (
    <Card className={clsx("p-4", c.needs_attention && "border-warn/40")}>
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate font-semibold">{c.name}</h3>
            {c.is_demo && <Badge>Demo</Badge>}
            <Badge tone={STAGE_TONE[c.stage] ?? "neutral"}>{c.stage}</Badge>
            {c.status !== "active" && <Badge tone="danger">{STATUS_LABEL[c.status]}</Badge>}
          </div>
          <p className="mt-0.5 text-xs text-muted">
            {c.id} · joined {ago(c.created_at)} · last activity {ago(c.last_activity)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {busy && <Loader2 size={14} className="animate-spin text-muted" aria-label="Saving" />}
          <label className="text-xs text-muted">Plan{" "}
            <select aria-label={`Plan for ${c.name}`} className={select} value={c.plan} disabled={busy}
              onChange={(e) => save({ plan: e.target.value })}>
              <option value="trial">Trial</option>
              <option value="pro">Pro</option>
              <option value="campus">Campus</option>
            </select>
          </label>
          <label className="text-xs text-muted">Status{" "}
            <select aria-label={`Status of ${c.name}`} className={select} value={c.status} disabled={busy || c.is_demo}
              title={c.is_demo ? "The demo college stays open for everyone" : undefined}
              onChange={(e) => save({ status: e.target.value })}>
              <option value="active">Active</option>
              <option value="read_only">Read-only</option>
              <option value="paused">Paused</option>
            </select>
          </label>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-center sm:grid-cols-6">
        {([["Sections", c.sections], ["Teachers", c.teachers], ["Students", c.students], ["Accounts", c.accounts],
          ["Classes", c.classes], ["Attendance", c.attendance_marked]] as const).map(([k, v]) => (
          <div key={k} className="rounded-lg bg-surface-2 px-2 py-1.5">
            <p className="text-sm font-semibold">{v.toLocaleString()}</p>
            <p className="text-[11px] text-muted">{k}</p>
          </div>
        ))}
      </div>

      {c.departments > 0 && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-muted">
            <span>Departments Ready</span><span>{c.departments_ready} of {c.departments}</span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={ready}
            aria-valuemin={0} aria-valuemax={100} aria-label="Departments Ready">
            <div className={clsx("h-full rounded-full", ready === 100 ? "bg-ok" : "bg-accent")} style={{ width: `${ready}%` }} />
          </div>
        </div>
      )}

      {c.flags.length > 0 ? (
        <ul className="mt-3 space-y-1 text-sm">
          {c.flags.map((f) => (
            <li key={f} className={clsx("flex gap-2", c.needs_attention ? "text-warn" : "text-muted")}>
              <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden /> {f}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 flex items-center gap-2 text-sm text-ok"><CheckCircle2 size={14} aria-hidden /> Healthy</p>
      )}

      <input aria-label={`Private note about ${c.name}`} value={note} maxLength={500} placeholder="Private note (e.g. demo booked for Friday)"
        onChange={(e) => setNote(e.target.value)} onBlur={() => note !== c.note && save({ note })}
        className="mt-3 w-full rounded-md border border-transparent bg-transparent px-2 py-1 text-xs text-muted hover:border-border focus:border-accent focus:outline-none" />
      {error && <p role="alert" className="mt-2 text-xs text-danger">{error}</p>}
    </Card>
  );
}
