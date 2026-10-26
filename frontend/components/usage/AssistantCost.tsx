"use client";

import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui";
import { api } from "@/lib/api";
import type { AssistantUsage, UsagePeriod } from "@/lib/types";

const inr = (n: number) => `₹${n < 10 ? n.toFixed(2) : Math.round(n).toLocaleString("en-IN")}`;

/** College Admin Home: what the AI assistant cost (Claude tokens), today / 7 days / this month. */
export function AssistantCostCard() {
  const [u, setU] = useState<AssistantUsage | null>(null);
  useEffect(() => { api.assistantUsage().then(setU).catch(() => setU(null)); }, []);
  if (!u) return null;
  const max = Math.max(...u.by_day.map((d) => d.usd), 0.0001);
  return (
    <Card className="mt-4 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold"><Sparkles size={16} className="text-accent-text" aria-hidden /> Assistant cost</h3>
        <span className="text-xs text-muted">{u.month.requests ? `about ${inr(u.per_answer_inr)} per answer` : "no answers yet this month"}</span>
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
        {([["Today", u.today], ["Last 7 days", u.week], ["This month", u.month]] as const).map(([k, p]) => (
          <div key={k} className="rounded-lg border border-border px-2 py-2">
            <dt className="text-xs text-muted">{k}</dt>
            <dd className="text-lg font-semibold">{inr(p.inr)}</dd>
            <dd className="text-[11px] text-muted">{p.requests} answer{p.requests === 1 ? "" : "s"} · ${p.usd.toFixed(2)}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-3 flex h-10 items-end gap-1" aria-label="Cost per day, last 14 days">
        {u.by_day.map((d) => (
          <div key={d.day} title={`${d.day}: ${d.requests} answers, $${d.usd.toFixed(3)}`}
            className="flex-1 rounded-sm bg-accent/60" style={{ height: `${Math.max(4, (d.usd / max) * 100)}%`, opacity: d.usd ? 1 : 0.25 }} />
        ))}
      </div>
      <p className="mt-2 text-[11px] text-muted">Claude tokens for the assistant, at Claude Opus 5.5 prices. Timetable generation never uses AI, so it costs nothing.</p>
    </Card>
  );
}

/** Platform owner: the assistant's cost per college this month. */
export function PlatformAssistantCost({ names }: { names: Record<string, string> }) {
  const [rows, setRows] = useState<Record<string, UsagePeriod> | null>(null);
  useEffect(() => { api.platformAssistantUsage().then(setRows).catch(() => setRows(null)); }, []);
  if (!rows) return null;
  const list = Object.entries(rows).sort((a, b) => b[1].usd - a[1].usd);
  const total = list.reduce((s, [, p]) => s + p.inr, 0);
  return (
    <Card className="mt-4 p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold"><Sparkles size={16} className="text-accent-text" aria-hidden /> Assistant cost this month</h3>
        <span className="text-sm font-semibold">{inr(total)}</span>
      </div>
      {list.length === 0 ? <p className="mt-2 text-sm text-muted">No assistant answers yet this month.</p> : (
        <ul className="mt-2 divide-y divide-border text-sm">
          {list.map(([org, p]) => (
            <li key={org} className="flex justify-between py-1.5">
              <span>{names[org] ?? org}</span>
              <span className="text-muted">{p.requests} answers · <span className="text-text">{inr(p.inr)}</span></span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
