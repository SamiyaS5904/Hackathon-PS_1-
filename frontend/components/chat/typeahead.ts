import type { College, Role } from "@/lib/types";

/** Ready-made requests for this person, filled with the college's real names. */
export function phrasebook(who: Role | "platform", college: College | null): string[] {
  const teachers = (college?.teachers ?? []).map((t) => t.name);
  const sections = (college?.sections ?? []).map((s) => s.name);
  const out: string[] = [];
  if (who === "platform") {
    return ["Which colleges need attention, and why?", "Who is stuck in onboarding?", "Which colleges are live?",
      "Pause a college", "Which colleges had no activity this week?"];
  }
  if (who === "admin" || who === "coordinator") {
    out.push("Who is away today, and which classes need cover?", "Undo the last change", "What changed this week?",
      "Which rooms are free right now?", "Any leave waiting for approval?", "Brief me on tomorrow",
      "Find a 1-period meeting time for my department's teachers this week", "Explain the quality score");
    for (const t of teachers) {
      out.push(`${t} is away tomorrow, plan cover`, `${t} is on leave for 3 days from Monday, substitutes for everyone`,
        `Show ${t}'s timetable`, `Where is ${t} right now?`);
    }
    for (const s of sections) {
      out.push(`Show ${s} timetable this week`, `Who is below 75% attendance in ${s}?`, `When is ${s} free tomorrow?`);
    }
  } else if (who === "teacher") {
    out.push("What do I teach tomorrow?", "When am I free tomorrow?", "I'm on leave tomorrow, ask my Coordinator",
      "Which classes haven't I marked attendance for?", "Find a makeup time for my cancelled lecture",
      "Cancel my lecture tomorrow", "Who has booked my office hours this week?", "Which rooms are free right now?");
    for (const t of teachers) out.push(`Where is ${t} right now?`);
  } else {
    out.push("What do I have tomorrow?", "What's my next class, and where?", "Are any of my classes cancelled this week?",
      "What's my attendance, and can I miss a class?", "When am I free tomorrow?", "Which rooms are free right now?",
      "Book a doubt slot this week");
    for (const t of teachers) out.push(`Where is ${t} right now?`, `Book a doubt slot with ${t}`);
  }
  return out;
}

/** Up to 3 phrases that match what is typed so far: every typed word must appear (the last one as a start). */
export function completions(typed: string, phrases: string[]): string[] {
  const words = typed.toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu, " ").split(/\s+/).filter(Boolean);
  if (!words.length || typed.trim().length < 2) return [];
  const last = words[words.length - 1];
  const rest = words.slice(0, -1);
  const out: string[] = [];
  for (const p of phrases) {
    const lower = p.toLowerCase();
    const pw = lower.replace(/[^\p{L}\p{N}\s-]/gu, " ").split(/\s+/);
    if (lower === typed.trim().toLowerCase()) continue;
    if (rest.every((w) => pw.some((x) => x.startsWith(w))) && pw.some((x) => x.startsWith(last))) {
      out.push(p);
      if (out.length === 3) break;
    }
  }
  return out;
}
