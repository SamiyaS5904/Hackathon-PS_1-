"use client";

import clsx from "clsx";
import { Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CollegeCard } from "@/components/platform/CollegeCard";
import { ErrorCard, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import type { CollegeSummary, PlatformOverview } from "@/lib/types";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "attention", label: "Needs attention" },
  { key: "live", label: "Live" },
  { key: "onboarding", label: "Onboarding" },
] as const;
type Filter = (typeof FILTERS)[number]["key"];

/** Platform owner (Super Admin): every college's health in one place. Plans and pauses, never college data. */
export default function PlatformPage() {
  const [data, setData] = useState<PlatformOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await api.platformOverview());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load the platform overview");
    }
  }, []);
  useEffect(() => {
    load();
    // The assistant can change a plan or status (the owner applies its card): show it right away.
    window.addEventListener("platform:changed", load);
    return () => window.removeEventListener("platform:changed", load);
  }, [load]);

  const items = useMemo(() => (data?.items ?? []).filter((c) =>
    (filter === "all" || (filter === "attention" && c.needs_attention) || (filter === "live" && c.stage === "Live")
      || (filter === "onboarding" && ["Setting up", "Collecting data", "Ready to generate"].includes(c.stage)))
    && (!query || `${c.name} ${c.id}`.toLowerCase().includes(query.toLowerCase()))), [data, filter, query]);

  const replace = (c: CollegeSummary) =>
    setData((d) => d && { ...d, items: d.items.map((x) => (x.id === c.id ? c : x)) });

  return (
    <div>
      <PageHeader title="Platform" subtitle="Every college on Timetabl.ai: how far each one is, how much it's used, and who needs a hand. You manage plans and access here; college data stays with each college." />
      {error && <ErrorCard message={error} onRetry={load} />}
      {!data ? !error && <Skeleton className="h-64 w-full" /> : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {([
              ["Colleges", data.colleges, `${data.live} live`],
              ["Need attention", data.needs_attention, "stuck or idle"],
              ["Students", data.students, `${data.accounts.toLocaleString()} accounts`],
              ["Classes scheduled", data.classes, `${data.attendance_marked.toLocaleString()} attendance sheets · ${data.bookings} bookings`],
            ] as const).map(([k, v, hint]) => (
              <div key={k} className={clsx("rounded-xl border bg-surface px-4 py-3",
                k === "Need attention" && v > 0 ? "border-warn/40" : "border-border")}>
                <p className="text-xs text-muted">{k}</p>
                <p className="mt-1 text-2xl font-semibold tracking-tight">{v.toLocaleString()}</p>
                <p className="text-xs text-muted">{hint}</p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">
            Plans: {Object.entries(data.plans).map(([p, n]) => `${n} ${p}`).join(" · ") || "none yet"}
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-2">
            <div className="flex rounded-lg border border-border bg-surface p-0.5" role="tablist" aria-label="Filter colleges">
              {FILTERS.map((f) => (
                <button key={f.key} role="tab" aria-selected={filter === f.key} onClick={() => setFilter(f.key)}
                  className={clsx("rounded-md px-3 py-1 text-sm", filter === f.key ? "bg-accent-soft font-medium text-accent-text" : "text-muted hover:text-text")}>
                  {f.label}
                </button>
              ))}
            </div>
            <div className="flex min-w-[12rem] flex-1 items-center gap-2 rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 sm:max-w-xs">
              <Search size={14} className="text-muted" aria-hidden />
              <input className="w-full bg-transparent text-sm outline-none" placeholder="Search colleges" value={query}
                onChange={(e) => setQuery(e.target.value)} aria-label="Search colleges" />
            </div>
          </div>

          <div className="mt-4 space-y-3">
            {items.length === 0 ? (
              <p className="rounded-xl border border-border bg-surface p-6 text-center text-sm text-muted">No college matches.</p>
            ) : items.map((c) => <CollegeCard key={c.id} c={c} onChange={replace} />)}
          </div>
        </>
      )}
    </div>
  );
}
