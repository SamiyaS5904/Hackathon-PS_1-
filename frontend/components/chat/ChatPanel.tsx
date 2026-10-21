"use client";

import clsx from "clsx";
import { ArrowRight, CheckCircle2, Loader2, Mic, MicOff, RotateCcw, Send, Sparkles, X, XCircle } from "lucide-react";
import { usePathname } from "next/navigation";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { isStaff, useAuth } from "@/lib/auth";
import { createRecognition, streamChat } from "@/lib/chat";
import { useChatPage } from "@/lib/chat-context";
import { useTimetable } from "@/lib/timetable-context";
import type { ChatCard, ChatEvent, Insight, Role } from "@/lib/types";

interface Msg {
  role: "user" | "assistant";
  text: string;
  tools: { label: string; status: "start" | "done" | "error" }[];
  cards: ChatCard[];
  error?: string;
}

const SUGGESTIONS: Record<Role, string[]> = {
  student: ["What do I have tomorrow?", "When is my next lab?", "When am I free next week to fix a meeting?",
    "Which rooms are free right now?"],
  teacher: ["What do I teach tomorrow?", "Cancel my lecture tomorrow, I'm on duty", "When is CSE-3A free this week for a makeup class?",
    "Where is Dr. Anita Sharma right now?"],
  coordinator: ["Which classes in my department still need attention?", "When is CSE-2A free on Friday?",
    "Move CSE-2A's Data Structures to Thursday morning", "Explain the quality score"],
  admin: ["Explain the quality score and what to improve", "Which departments aren't Ready yet?",
    "Which rooms are almost unused?", "Rebalance the busiest teacher's week"],
};

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
  const { setData } = useTimetable();
  const { page, open, setOpen, pending, clearPending } = useChatPage();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [convId, setConvId] = useState<string | null>(null);
  const [insights, setInsights] = useState<Insight[] | null>(null);
  const [listening, setListening] = useState(false);
  const [voice, setVoice] = useState(false);
  const recRef = useRef<ReturnType<typeof createRecognition>>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setVoice(createRecognition() !== null);
  }, []);
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

  const send = useCallback(async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    setMsgs((m) => [...m, { role: "user", text: q, tools: [], cards: [] },
      { role: "assistant", text: "", tools: [], cards: [] }]);
    const update = (fn: (m: Msg) => Msg) => setMsgs((all) => [...all.slice(0, -1), fn(all[all.length - 1])]);
    await streamChat(q, convId, { path, ...page }, (e: ChatEvent) => {
      if (e.type === "start") setConvId(e.conversation_id);
      else if (e.type === "token") update((m) => ({ ...m, text: m.text + e.text }));
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
    });
    setBusy(false);
  }, [busy, convId, path, page]);

  // Questions sent from elsewhere (e.g. an insight's "Ask" button).
  useEffect(() => {
    if (pending && open && !busy) {
      send(pending);
      clearPending();
    }
  }, [pending, open, busy, send, clearPending]);

  const toggleMic = () => {
    if (listening) {
      recRef.current?.stop();
      return;
    }
    const r = createRecognition();
    if (!r) return;
    recRef.current = r;
    const base = input ? `${input} ` : "";
    r.onresult = (e) => {
      const said = Array.from(e.results).map((res) => res[0].transcript).join("");
      setInput(base + said);
    };
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    setListening(true);
    r.start();
  };

  const reset = () => {
    setMsgs([]);
    setConvId(null);
  };

  if (!role) return null;

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
                {page.entity ? `Looking at ${page.entity}` : "Answers from your timetable"} · changes need your Apply
              </p>
            </div>
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
                  Hi {user?.name.split(" ")[0]}. Ask about your timetable in plain words{voice ? ", or tap the mic and speak" : ""}.
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
                  {SUGGESTIONS[role].map((s) => (
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
                {m.cards.map((c, j) => <CardView key={j} card={c} onApplied={(out) => out && setData(out)} />)}
                {m.error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-danger">{m.error}</p>}
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <form className="border-t border-border p-3" onSubmit={(e) => { e.preventDefault(); send(input); }}>
            <div className="flex items-end gap-2 rounded-xl border border-border-strong bg-surface px-3 py-2 focus-within:border-accent">
              <textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} rows={1} maxLength={2000}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
                placeholder={listening ? "Listening…" : "Ask about your timetable…"} aria-label="Message"
                className="max-h-32 min-h-[24px] flex-1 resize-none bg-transparent text-sm outline-none" />
              {voice && (
                <button type="button" onClick={toggleMic} aria-label={listening ? "Stop listening" : "Speak your question"}
                  aria-pressed={listening}
                  className={clsx("rounded-full p-2 transition", listening ? "animate-pulse bg-danger-soft text-danger" : "text-muted hover:bg-surface-2")}>
                  {listening ? <MicOff size={16} /> : <Mic size={16} />}
                </button>
              )}
              <button type="submit" disabled={busy || !input.trim()} aria-label="Send"
                className="rounded-full bg-accent p-2 text-white transition disabled:opacity-40 dark:text-bg">
                {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </button>
            </div>
            <p className="mt-1.5 px-1 text-[11px] text-muted">Answers come from your timetable. Nothing changes until you click Apply.</p>
          </form>
        </aside>
      )}
    </>
  );
}

function CardView({ card, onApplied }: { card: ChatCard; onApplied: (out: Parameters<ReturnType<typeof useTimetable>["setData"]>[0] | null) => void }) {
  const [state, setState] = useState<"ready" | "busy" | "applied" | "discarded" | "error">("ready");
  const [message, setMessage] = useState("");

  const apply = async () => {
    setState("busy");
    try {
      if (card.type === "proposal") {
        onApplied(await api.apply(card.proposal.id));
        setMessage("Applied. The timetable is updated and the change is in Activity (undo is there too).");
      } else {
        const a = card.action;
        const out = await api.addOverride({ session_id: a.session_id, date: a.date, kind: a.kind, to_date: a.to_date,
          start_period: a.start_period, reason: a.reason });
        onApplied(out.timetable);
        setMessage(out.message);
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

  return (
    <div className="rounded-xl border border-accent/30 bg-accent-soft/40 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-accent-text">
        {card.type === "proposal" ? "Permanent change · checked for clashes" : "One-day change"}
      </p>
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
        <p className="mt-1 text-sm">{card.action.summary}</p>
      )}
      {state === "applied" || state === "error" ? (
        <p className={clsx("mt-2 text-xs", state === "applied" ? "text-ok" : "text-danger")}>{message}</p>
      ) : state === "discarded" ? (
        <p className="mt-2 text-xs text-muted">Discarded. Nothing changed.</p>
      ) : (
        <div className="mt-3 flex gap-2">
          <Button variant="primary" onClick={apply} disabled={state === "busy"} className="px-3 py-1.5 text-xs">
            {state === "busy" && <Loader2 size={14} className="animate-spin" />} Apply
          </Button>
          <Button onClick={discard} disabled={state === "busy"} className="px-3 py-1.5 text-xs">Discard</Button>
        </div>
      )}
    </div>
  );
}
