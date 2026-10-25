"use client";

import { CheckCircle2, ChevronDown, Loader2, RefreshCw, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { GENERATE_SECONDS, isGenerating, useTimetable } from "@/lib/timetable-context";

/** Generate (first time) or Regenerate. Regenerating asks: keep the current timetable, or start fresh? */
export function GenerateButton({ label, primary = true }: { label?: string; primary?: boolean }) {
  const { generate, job, data, precheck, college } = useTimetable();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const running = isGenerating(job);
  const blocked = (precheck?.problems.length ?? 0) > 0;

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const disabled = running || blocked || !college;
  const icon = running ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Sparkles size={16} aria-hidden />;
  if (!data) {
    return (
      <Button variant={primary ? "primary" : "secondary"} onClick={() => generate()} disabled={disabled}
        title={blocked ? "Fix the data problems first" : undefined}>
        {icon} {running ? "Generating…" : (label ?? "Generate timetable")}
      </Button>
    );
  }
  const run = (keep: boolean) => {
    setOpen(false);
    generate(keep);
  };
  return (
    <div className="relative" ref={ref}>
      <Button variant={primary ? "primary" : "secondary"} onClick={() => setOpen(!open)} disabled={disabled}
        aria-haspopup="menu" aria-expanded={open} title={blocked ? "Fix the data problems first" : undefined}>
        {icon} {running ? "Generating…" : (label ?? "Regenerate")} {!running && <ChevronDown size={14} aria-hidden />}
      </Button>
      {open && (
        <div role="menu" className="absolute right-0 z-30 mt-2 w-80 rounded-xl border border-border bg-surface p-1.5 shadow-xl">
          <button role="menuitem" onClick={() => run(true)} className="w-full rounded-lg px-3 py-2.5 text-left hover:bg-surface-2">
            <span className="flex items-center gap-2 text-sm font-medium"><RefreshCw size={15} className="text-accent-text" aria-hidden />
              Keep the current timetable {data.ever_published && <span className="rounded bg-accent-soft px-1.5 text-[10px] text-accent-text">Recommended</span>}</span>
            <span className="mt-0.5 block text-xs text-muted">Only classes that must change move; everyone keeps their week. Best mid-semester.</span>
          </button>
          <button role="menuitem" onClick={() => run(false)} className="w-full rounded-lg px-3 py-2.5 text-left hover:bg-surface-2">
            <span className="flex items-center gap-2 text-sm font-medium"><Sparkles size={15} className="text-muted" aria-hidden /> Start fresh</span>
            <span className="mt-0.5 block text-xs text-muted">Best possible quality, but most classes may move. Best before the semester starts.</span>
          </button>
        </div>
      )}
    </div>
  );
}

export function GenerationProgress() {
  const { job, notice, clearNotice } = useTimetable();
  if (!isGenerating(job)) {
    if (!notice) return null;
    return (
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-ok/30 bg-ok-soft p-4 text-sm text-ok" role="status">
        <CheckCircle2 size={18} className="mt-0.5 shrink-0" aria-hidden />
        <p className="flex-1"><b>Regenerated with minimal change.</b> {notice} Review it, then publish to tell everyone.</p>
        <button onClick={clearNotice} aria-label="Dismiss" className="rounded p-1 hover:bg-ok/10"><X size={14} /></button>
      </div>
    );
  }
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
