"use client";

import { Check, Sparkles } from "lucide-react";
import { useChatPage } from "@/lib/chat-context";
import type { College, MoveOption, Session } from "@/lib/types";

const SHOWN = 6;

/** "Ask the assistant" with a ready-made question the person can check and send. */
export function AskAssistant({ text, label, before }: { text: string; label: string; before?: () => void }) {
  const { prefill } = useChatPage();
  return (
    <button type="button" onClick={() => { before?.(); prefill(text); }}
      className="inline-flex items-center gap-1.5 text-xs font-medium text-accent-text hover:underline">
      <Sparkles size={13} aria-hidden /> {label}
    </button>
  );
}

/** While a class is being moved: the best slots spelled out (teacher, students and a room all free), so nobody has
 *  to hunt across the grid. A click is the same as dropping the class there. */
export function MoveSuggestions({ college, moving, options, busy, requestOnly, onPick }: {
  college: College;
  moving: Session;
  options: Map<string, MoveOption>;
  busy: boolean;
  requestOnly: boolean;
  onPick: (day: string, start: string) => void;
}) {
  const all = [...options.values()];
  const dayIndex = (d: string) => college.days.indexOf(d);
  const free = all.filter((o) => o.status === "free")
    .sort((a, b) => Number(a.venue_id !== moving.venue_id) - Number(b.venue_id !== moving.venue_id)
      || dayIndex(a.day) - dayIndex(b.day) || a.start_period - b.start_period);
  const repair = all.filter((o) => o.status === "repair").length;
  const subject = college.subjects.find((s) => s.id === moving.subject_id)?.name ?? "this class";
  const sections = moving.section_ids.map((id) => college.sections.find((s) => s.id === id)?.name).filter(Boolean).join(" + ");
  const room = (id: string | null) => college.venues.find((v) => v.id === id)?.name ?? "";
  const ask = `Find the best time to move ${subject} (${sections}, now ${moving.day} ${moving.start}). `
    + "The teacher, every student and a room must be free.";

  return (
    <div className="no-print mb-3 rounded-lg border border-border bg-surface p-3">
      <p className="text-sm font-medium">
        {free.length ? "Suggested slots" : "No slot is fully free this week"}
        <span className="ml-2 font-normal text-muted">
          {free.length
            ? `Teacher, students and a room all free${requestOnly ? ". Pick one to ask your Department Coordinator" : ""}.`
            : repair ? "Amber slots work if other classes shift." : "Try another week day or ask the assistant."}
        </span>
      </p>
      {free.length > 0 && (
        <div className="mt-2.5 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {free.slice(0, SHOWN).map((o) => (
            <button key={`${o.day}|${o.start}`} type="button" disabled={busy} onClick={() => onPick(o.day, o.start)}
              className="rounded-lg border border-ok/40 bg-ok-soft px-3 py-2 text-left text-xs text-ok transition hover:ring-2 hover:ring-ok/40 disabled:opacity-60">
              <span className="block text-sm font-semibold">{o.day} · {o.start}–{o.end}</span>
              <span className="mt-0.5 flex flex-wrap items-center gap-x-2 opacity-90">
                <span className="inline-flex items-center gap-0.5"><Check size={11} aria-hidden /> Teacher</span>
                <span className="inline-flex items-center gap-0.5"><Check size={11} aria-hidden /> Students</span>
                <span>{room(o.venue_id)}{o.venue_id !== moving.venue_id ? " (new room)" : ""}</span>
              </span>
            </button>
          ))}
        </div>
      )}
      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
        {free.length > SHOWN && <span>{free.length - SHOWN} more green slots on the grid</span>}
        {free.length > 0 && repair > 0 && <span>{repair} more if other classes shift (amber)</span>}
        <AskAssistant text={ask} label={free.length ? "None of these suits? Ask the assistant" : "Ask the assistant to find a way"} />
      </div>
    </div>
  );
}
