"use client";

import clsx from "clsx";
import { ArrowRight, CheckCircle2, Loader2, Mic, RotateCcw, Send, Sparkles, Square, Volume2, VolumeX, X, XCircle } from "lucide-react";
import { usePathname } from "next/navigation";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { isStaff, useAuth } from "@/lib/auth";
import { createRecognition, speak, stopSpeaking, streamChat, voiceErrorText } from "@/lib/chat";
import { useChatPage } from "@/lib/chat-context";
import { useTimetableOptional } from "@/lib/timetable-context";
import { useToast } from "@/lib/toast";
import type { ChatCard, ChatEvent, Insight, Role, TimetableOut } from "@/lib/types";

interface Msg {
  role: "user" | "assistant";
  text: string;
  tools: { label: string; status: "start" | "done" | "error" }[];
  cards: ChatCard[];
  error?: string;
}

/** Fallback questions per role (pages usually supply their own). Names come from this college's data. */
function defaultSuggestions(who: Role | "platform", section: string, teacher: string): string[] {
  switch (who) {
    case "platform":
      return ["Which colleges need attention, and why?", "Who is stuck in onboarding?", "Which colleges had no activity this week?"];
    case "student":
      return ["What do I have tomorrow?", "What's my attendance, and can I miss a class?", "Which rooms are free right now?"];
    case "teacher":
      return ["What do I teach tomorrow?", "Which classes haven't I marked attendance for?",
        teacher ? `Where is ${teacher} right now?` : "Which rooms are free right now?"];
    case "coordinator":
      return ["Who is away today, and which classes need cover?",
        section ? `Who is below 75% attendance in ${section}?` : "Which classes in my department still need attention?",
        "When are all my department's teachers free for a meeting this week?"];
    default:
      return ["Who is away today, and which classes need cover?", "Explain the quality score and what to improve",
        "Which rooms are almost unused?"];
  }
}

/** Tiny formatter: **bold**, "- " bullets and line breaks. The model's text is never rendered as HTML. */
function Rich({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        const bullet = /^\s*[-*•]\s+/.test(line);
        const content = line.replace(/^\s*[-*•]\s+/, "");
        const parts = content.split(/(\*\*[^*]+\*\*)/g).map((p, j) =>
          p.startsWith("**") && p.endsWith("**") ? <b key={j}>{p.slice(2, -2)}</b> : <Fragment key={j}>{p}</Fragment>);
        if (!line.trim()) return <div key={i} className="h-1" />;
        return bullet ? (
          <div key={i} className="flex gap-2"><span className="text-muted">•</span><span>{parts}</span></div>
        ) : <p key={i}>{parts}</p>;
      })}
    </div>
  );
}

export function ChatPanel() {
  const path = usePathname();
  const { role, user } = useAuth();
  const tt = useTimetableOptional();
  const setData = tt?.setData;
  const college = tt?.college ?? null;
  // The platform owner's assistant (on the platform page, outside any college).
  const platform = !role && !!user?.platform_owner;
  const who = platform ? "platform" : role;
  const { page, open, setOpen, pending, clearPending, draft, clearDraft } = useChatPage();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [convId, setConvId] = useState<string | null>(null);
  const [insights, setInsights] = useState<Insight[] | null>(null);
  const [listening, setListening] = useState(false);
  const [voice, setVoice] = useState(false);
  const [heard, setHeard] = useState(""); // live transcript while speaking
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [speakReplies, setSpeakReplies] = useState(true); // replies to spoken questions are read aloud
  const [speaking, setSpeaking] = useState(false);
  const recRef = useRef<ReturnType<typeof createRecognition>>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setVoice(createRecognition() !== null);
    try {
      setSpeakReplies(localStorage.getItem("tt-speak-replies") !== "0");
    } catch {
      /* storage blocked: keep the default */
    }
  }, []);
  useEffect(() => {
    if (!open) {
      recRef.current?.stop();
      stopSpeaking();
      setSpeaking(false);
    }
  }, [open]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!open);
      } else if (e.key === "Escape" && open) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);
  useEffect(() => {
    if (open && isStaff(role) && insights === null) api.insights().then(setInsights).catch(() => setInsights([]));
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open, role, insights]);
  useEffect(() => {
    // Braces matter: newer browsers return a Promise from scrollIntoView, and an effect must return nothing.
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  const send = useCallback(async (text: string, spoken = false) => {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    setVoiceError(null);
    stopSpeaking();
    setSpeaking(false);
    setBusy(true);
    let answer = "";
    setMsgs((m) => [...m, { role: "user", text: q, tools: [], cards: [] },
      { role: "assistant", text: "", tools: [], cards: [] }]);
    const update = (fn: (m: Msg) => Msg) => setMsgs((all) => [...all.slice(0, -1), fn(all[all.length - 1])]);
    await streamChat(q, convId, { path, view: page.view, entity: page.entity, mode: page.mode }, (e: ChatEvent) => {
      if (e.type === "start") setConvId(e.conversation_id);
      else if (e.type === "token") {
        answer += e.text;
        update((m) => ({ ...m, text: m.text + e.text }));
      }
      else if (e.type === "tool")
        update((m) => {
          const tools = [...m.tools];
          const last = tools.findIndex((t) => t.label === e.label && t.status === "start");
          if (e.status === "start") tools.push({ label: e.label, status: "start" });
          else if (last >= 0) tools[last] = { label: e.label, status: e.status };
          return { ...m, tools };
        });
      else if (e.type === "card") update((m) => ({ ...m, cards: [...m.cards, e.card] }));
      else if (e.type === "error") update((m) => ({ ...m, error: e.message }));
    }, { voice: spoken, org: platform ? "platform" : undefined });
    setBusy(false);
    // Spoken question -> spoken answer (the text stays on screen too).
    if (spoken && speakReplies && speak(answer, () => setSpeaking(false))) setSpeaking(true);
  }, [busy, convId, path, page, speakReplies, platform]);

  // A message typed in from elsewhere (e.g. Home's "Handle with assistant"): the user checks it and sends.
  useEffect(() => {
    if (draft && open) {
      setInput(draft);
      clearDraft();
      setTimeout(() => inputRef.current?.focus(), 60);
    }
  }, [draft, open, clearDraft]);

  // Questions sent from elsewhere (e.g. an insight's "Ask" button).
  useEffect(() => {
    if (pending && open && !busy) {
      send(pending);
      clearPending();
    }
  }, [pending, open, busy, send, clearPending]);

  // Tap the mic, speak (English or Hinglish), pause: the question is sent by itself. Tap again to send early.
  const toggleMic = () => {
    if (listening) {
      recRef.current?.stop();
      return;
    }
    const r = createRecognition();
    if (!r) return;
    stopSpeaking();
    setSpeaking(false);
    setVoiceError(null);
    recRef.current = r;
    const base = input.trim() ? `${input.trim()} ` : "";
    let said = "";
    r.onresult = (e) => {
      said = Array.from(e.results).map((res) => res[0].transcript).join("");
      setHeard(said);
    };
    r.onerror = (e) => setVoiceError(voiceErrorText(e.error));
    r.onend = () => {
      setListening(false);
      setHeard("");
      if (said.trim()) send(base + said, true);
    };
    setListening(true);
    try {
      r.start();
    } catch {
      setListening(false);
    }
  };

  const toggleSpeakReplies = () => {
    const next = !speakReplies;
    setSpeakReplies(next);
    if (!next) {
      stopSpeaking();
      setSpeaking(false);
    }
    try {
      localStorage.setItem("tt-speak-replies", next ? "1" : "0");
    } catch {
      /* storage blocked: the choice lasts for this visit */
    }
  };

  const reset = () => {
    setMsgs([]);
    setConvId(null);
  };

  if (!who) return null;
  const suggestions = (page.suggestions?.length ? page.suggestions
    : defaultSuggestions(who, college?.sections[0]?.name ?? "", college?.teachers[0]?.name ?? "")).slice(0, 3);

  return (
    <>
      {!open && (
        <button onClick={() => setOpen(true)} aria-label="Open the assistant (Ctrl+K)"
          className="no-print fixed bottom-5 right-5 z-30 flex items-center gap-2 rounded-full border border-border-strong bg-surface px-4 py-2.5 text-sm font-medium shadow-lg transition hover:bg-surface-2">
          <Sparkles size={16} className="text-accent-text" aria-hidden /> Ask
          <kbd className="hidden rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-muted sm:inline">Ctrl K</kbd>
        </button>
      )}
      {open && (
        <aside className="no-print fixed inset-y-0 right-0 z-40 flex w-full max-w-md flex-col border-l border-border bg-surface shadow-2xl"
          role="dialog" aria-label="Assistant">
          <div className="flex items-center gap-2 border-b border-border px-4 py-3">
            <Sparkles size={18} className="text-accent-text" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">Assistant</p>
              <p className="truncate text-xs text-muted">
                {platform ? "Answers from the platform" : page.entity ? `Looking at ${page.entity}` : "Answers from your timetable"} · changes need your Apply
              </p>
            </div>
            {voice && (
              <button onClick={toggleSpeakReplies} aria-pressed={speakReplies}
                aria-label={speakReplies ? "Don't read answers aloud" : "Read answers to spoken questions aloud"}
                title={speakReplies ? "Answers to spoken questions are read aloud" : "Answers are not read aloud"}
                className="rounded p-1.5 text-muted hover:bg-surface-2">
                {speakReplies ? <Volume2 size={16} /> : <VolumeX size={16} />}
              </button>
            )}
            {msgs.length > 0 && (
              <button onClick={reset} aria-label="New conversation" title="New conversation"
                className="rounded p-1.5 text-muted hover:bg-surface-2"><RotateCcw size={16} /></button>
            )}
            <button onClick={() => setOpen(false)} aria-label="Close assistant" className="rounded p-1.5 text-muted hover:bg-surface-2">
              <X size={18} />
            </button>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4" aria-live="polite">
            {msgs.length === 0 && (
              <div className="space-y-4">
                <p className="text-sm text-muted">
                  Hi {user?.name.split(" ")[0]}. {platform ? "Ask about the colleges on the platform" : "Ask about your timetable"} in plain words
                  {voice ? ", or tap the mic and speak" : ""}. English or Hinglish both work: I answer in the language you use.
                </p>
                {insights && insights.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted">Worth a look</p>
                    {insights.map((i) => (
                      <button key={i.title} onClick={() => send(i.ask)}
                        className={clsx("w-full rounded-lg border px-3 py-2 text-left text-sm transition hover:bg-surface-2",
                          i.severity === "warn" ? "border-warn/40" : "border-border")}>
                        <span className="block font-medium">{i.title}</span>
                        <span className="block text-xs text-muted">{i.detail}</span>
                      </button>
                    ))}
                  </div>
                )}
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted">Try asking</p>
                  {suggestions.map((s) => (
                    <button key={s} onClick={() => send(s)}
                      className="flex w-full items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-left text-sm hover:bg-surface-2">
                      {s} <ArrowRight size={14} className="shrink-0 text-muted" />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {msgs.map((m, i) => m.role === "user" ? (
              <div key={i} className="ml-8 rounded-2xl rounded-br-sm bg-accent-soft px-3.5 py-2 text-sm text-text">{m.text}</div>
            ) : (
              <div key={i} className="mr-4 space-y-2 text-sm">
                {m.tools.length > 0 && (
                  <ul className="space-y-1">
                    {m.tools.map((t, j) => (
                      <li key={j} className="flex items-center gap-2 text-xs text-muted">
                        {t.status === "start" ? <Loader2 size={12} className="animate-spin" /> :
                          t.status === "done" ? <CheckCircle2 size={12} className="text-ok" /> : <XCircle size={12} className="text-warn" />}
                        {t.label}
                      </li>
                    ))}
                  </ul>
                )}
                {m.text ? <Rich text={m.text} /> : !m.error && busy && i === msgs.length - 1 && m.tools.length === 0 && (
                  <p className="flex items-center gap-2 text-muted"><Loader2 size={14} className="animate-spin" /> Thinking…</p>
                )}
                {m.cards.map((c, j) => <CardView key={j} card={c} onApplied={(out) => out && setData?.(out)} />)}
                {m.error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-danger">{m.error}</p>}
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <form className="border-t border-border p-3" onSubmit={(e) => { e.preventDefault(); send(input); }}>
            {listening && (
              <div className="mb-2 flex items-center gap-2 rounded-lg bg-danger-soft/60 px-3 py-2 text-sm" role="status">
                <span className="relative flex h-2.5 w-2.5 shrink-0">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-danger opacity-60" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-danger" />
                </span>
                <span className="min-w-0 flex-1 truncate">{heard || <span className="text-muted">Listening… speak in English or Hinglish</span>}</span>
                <button type="button" onClick={toggleMic} className="shrink-0 text-xs font-medium text-danger hover:underline">
                  {heard ? "Send now" : "Cancel"}
                </button>
              </div>
            )}
            {speaking && !listening && (
              <div className="mb-2 flex items-center gap-2 rounded-lg bg-accent-soft px-3 py-2 text-sm text-accent-text" role="status">
                <Volume2 size={15} className="shrink-0" aria-hidden />
                <span className="flex-1">Reading the answer aloud</span>
                <button type="button" onClick={() => { stopSpeaking(); setSpeaking(false); }}
                  className="flex items-center gap-1 text-xs font-medium hover:underline">
                  <Square size={11} aria-hidden /> Stop
                </button>
              </div>
            )}
            {voiceError && !listening && <p className="mb-2 rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn" role="alert">{voiceError}</p>}
            <div className="flex items-end gap-2 rounded-xl border border-border-strong bg-surface px-3 py-2 focus-within:border-accent">
              <textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} rows={1} maxLength={2000}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
                placeholder={listening ? "Listening…" : platform ? "Ask about the colleges…" : "Ask about your timetable…"} aria-label="Message"
                className="max-h-32 min-h-[24px] flex-1 resize-none bg-transparent text-sm outline-none" />
              {voice && (
                <button type="button" onClick={toggleMic} aria-label={listening ? "Stop listening" : "Speak your question"}
                  aria-pressed={listening}
                  className={clsx("rounded-full p-2 transition", listening ? "animate-pulse bg-danger-soft text-danger" : "text-muted hover:bg-surface-2")}>
                  {listening ? <Square size={14} /> : <Mic size={16} />}
                </button>
              )}
              <button type="submit" disabled={busy || !input.trim()} aria-label="Send"
                className="rounded-full bg-accent p-2 text-white transition disabled:opacity-40 dark:text-bg">
                {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </button>
            </div>
            <p className="mt-1.5 px-1 text-[11px] text-muted">Answers come from {platform ? "the platform" : "your timetable"}. Nothing changes until you click Apply.</p>
          </form>
        </aside>
      )}
    </>
  );
}

function CardView({ card, onApplied }: { card: ChatCard; onApplied: (out: TimetableOut | null) => void }) {
  const [state, setState] = useState<"ready" | "busy" | "applied" | "discarded" | "error">("ready");
  const [message, setMessage] = useState("");
  const showToast = useToast();

  const apply = async () => {
    setState("busy");
    try {
      if (card.type === "proposal") {
        const out = await api.apply(card.proposal.id);
        onApplied(out);
        setMessage("Applied. The timetable is updated and everyone affected is told.");
        showToast({ text: "Change applied.", undoEntryId: out.last_change?.id, onUndone: (o) => onApplied(o) });
      } else if (card.type === "platform") {
        const c = card.change;
        await api.updateCollege(c.org, { ...(c.plan ? { plan: c.plan } : {}), ...(c.status ? { status: c.status } : {}),
          ...(c.note !== null ? { note: c.note } : {}) });
        window.dispatchEvent(new Event("platform:changed"));
        setMessage(`Saved: ${c.summary}.`);
      } else if (card.type === "booking") {
        const b = card.booking;
        const out = b.kind === "doubt"
          ? await api.bookDoubt({ office_hour_id: b.office_hour_id ?? "", date: b.date, topic: b.topic ?? "" })
          : await api.bookMeeting({ teacher_ids: b.teacher_ids ?? [], date: b.date, start: b.start ?? "",
            end: b.end ?? "", title: b.title ?? "", place: b.place ?? "" });
        setMessage(`${out.message} It's on your Bookings page.`);
      } else {
        const a = card.action;
        const out = await api.addOverride({ session_id: a.session_id, date: a.date, kind: a.kind, to_date: a.to_date,
          start_period: a.start_period, reason: a.reason, via: "chatbot" });
        onApplied(out.timetable);
        setMessage(out.message);
        showToast({ text: out.message, undoEntryId: out.timetable.last_change?.id, onUndone: (o) => onApplied(o) });
      }
      setState("applied");
    } catch (e) {
      setState("error");
      setMessage(e instanceof Error ? e.message : "Couldn't apply");
    }
  };
  const discard = () => {
    if (card.type === "proposal") api.discard(card.proposal.id);
    setState("discarded");
  };
  const heading = card.type === "platform" ? `College settings · ${state === "applied" ? "saved" : "not saved yet"}`
    : card.type === "proposal" ? "Permanent change · checked for clashes"
    : card.type === "booking"
      ? `${card.booking.kind === "doubt" ? "Doubt slot" : "Meeting"} · ${state === "applied" ? "booked" : "not booked yet"}`
      : "One-day change";

  return (
    <div className="rounded-xl border border-accent/30 bg-accent-soft/40 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-accent-text">{heading}</p>
      {card.type === "proposal" ? (
        <ul className="mt-2 space-y-1.5 text-xs">
          {card.proposal.changes.map((c) => (
            <li key={c.session_id}>
              <span className="font-medium">{c.subject}</span> <span className="text-muted">{c.sections}</span>
              <div className="mt-0.5 flex flex-wrap items-center gap-1">
                <span className="rounded bg-danger-soft px-1.5 text-danger line-through">{c.before}</span>
                <ArrowRight size={11} className="text-muted" />
                <span className="rounded bg-ok-soft px-1.5 text-ok">{c.after}</span>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-sm">{card.type === "booking" ? card.booking.summary
          : card.type === "platform" ? card.change.summary : card.action.summary}</p>
      )}
      {state === "applied" || state === "error" ? (
        <p className={clsx("mt-2 text-xs", state === "applied" ? "text-ok" : "text-danger")}>{message}</p>
      ) : state === "discarded" ? (
        <p className="mt-2 text-xs text-muted">Discarded. Nothing changed.</p>
      ) : (
        <div className="mt-3 flex gap-2">
          <Button variant="primary" onClick={apply} disabled={state === "busy"} className="px-3 py-1.5 text-xs">
            {state === "busy" && <Loader2 size={14} className="animate-spin" />} {card.type === "booking" ? "Book" : "Apply"}
          </Button>
          <Button onClick={discard} disabled={state === "busy"} className="px-3 py-1.5 text-xs">Discard</Button>
        </div>
      )}
    </div>
  );
}
