"use client";

import clsx from "clsx";
import { ArrowRight, CheckCircle2, Circle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui";
import { api } from "@/lib/api";
import { useTimetable } from "@/lib/timetable-context";
import type { SetupStatus } from "@/lib/types";

/** Admin home, until the college is fully set up: seven steps, what's missing in each, and where to fix it. */
export function SetupChecklist() {
  const { college, data } = useTimetable();
  const [status, setStatus] = useState<SetupStatus | null>(null);

  useEffect(() => {
    api.setupStatus().then(setStatus).catch(() => setStatus(null));
  }, [college, data]);

  if (!status || status.done) return null;
  const done = status.steps.filter((s) => s.done).length;
  const nextKey = status.steps.find((s) => !s.done)?.key;
  return (
    <Card className="mb-6 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Get your college ready</h2>
        <span className="text-sm text-muted">{done} of {status.steps.length} done</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-label="Setup progress"
        aria-valuenow={done} aria-valuemin={0} aria-valuemax={status.steps.length}>
        <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${(100 * done) / status.steps.length}%` }} />
      </div>
      <ol className="mt-4 space-y-1">
        {status.steps.map((s, i) => {
          const next = s.key === nextKey;
          return (
            <li key={s.key} className={clsx("flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg px-2 py-2", next && "bg-accent-soft/60")}>
              {s.done
                ? <CheckCircle2 size={18} className="shrink-0 text-ok" aria-label="Done" />
                : <Circle size={18} className={clsx("shrink-0", next ? "text-accent-text" : "text-muted")} aria-label="Not done" />}
              <span className={clsx("text-sm", s.done ? "text-muted" : "font-medium")}>{i + 1}. {s.title}</span>
              {!s.done && s.missing && <span className="min-w-0 flex-1 text-xs text-muted">{s.missing}</span>}
              {!s.done && (
                <Link href={s.link} className={clsx("ml-auto inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium",
                  next ? "bg-accent text-white hover:bg-accent/90 dark:text-bg" : "text-accent-text hover:underline")}>
                  {next ? "Do this next" : "Fix"} <ArrowRight size={12} aria-hidden />
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
