"use client";

import { Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui";
import { GENERATE_SECONDS, isGenerating, useTimetable } from "@/lib/timetable-context";

export function GenerateButton({ label }: { label?: string }) {
  const { generate, job, data, precheck, college } = useTimetable();
  const running = isGenerating(job);
  const blocked = (precheck?.problems.length ?? 0) > 0;
  return (
    <Button
      variant="primary"
      onClick={generate}
      disabled={running || blocked || !college}
      title={blocked ? "Fix the data problems first" : undefined}
    >
      {running ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Sparkles size={16} aria-hidden />}
      {running ? "Generating…" : (label ?? (data ? "Regenerate" : "Generate timetable"))}
    </Button>
  );
}

export function GenerationProgress() {
  const { job } = useTimetable();
  if (!isGenerating(job)) return null;
  const pct = Math.min(100, ((job?.elapsed ?? 0) / GENERATE_SECONDS) * 100);
  return (
    <div className="mb-6 rounded-xl border border-accent/30 bg-accent-soft p-4" role="status" aria-live="polite">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-accent-text">
          Building a clash-free timetable and improving its quality…
        </span>
        <span className="font-mono text-xs text-accent-text">{job?.elapsed.toFixed(0)}s / ~{GENERATE_SECONDS}s</span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-accent/15">
        <div className="h-full rounded-full bg-accent transition-all duration-1000" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 text-xs text-accent-text/80">
        A valid timetable is found in seconds; the remaining time is spent reducing gaps, balancing teacher load and
        fitting rooms.
      </p>
    </div>
  );
}
