import { getSession } from "./api";
import type { ChatEvent } from "./types";

const CHATBOT = process.env.NEXT_PUBLIC_CHATBOT_URL ?? "http://localhost:8001";

export interface PageInfo {
  path: string;
  view?: string;
  entity?: string;
  mode?: string;
}

const pad = (n: number) => String(n).padStart(2, "0");

/** Send one message; calls onEvent for every streamed event. Resolves when the stream ends. */
export async function streamChat(
  message: string,
  conversationId: string | null,
  page: PageInfo,
  onEvent: (e: ChatEvent) => void,
  opts: { signal?: AbortSignal; voice?: boolean } = {},
): Promise<void> {
  const { token, org } = getSession();
  const now = new Date();
  let res: Response;
  try {
    res = await fetch(`${CHATBOT}/chat`, {
      method: "POST",
      signal: opts.signal,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        org, message, conversation_id: conversationId, page, voice: !!opts.voice,
        today: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`,
        now: `${pad(now.getHours())}:${pad(now.getMinutes())}`,
      }),
    });
  } catch {
    onEvent({ type: "error", message: "Can't reach the assistant. Is the assistant service running?" });
    onEvent({ type: "done" });
    return;
  }
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}));
    onEvent({ type: "error", message: typeof body.detail === "string" ? body.detail : `Assistant error (${res.status})` });
    onEvent({ type: "done" });
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(6)) as ChatEvent);
      } catch {
        /* ignore a malformed chunk */
      }
    }
  }
}

/** Browser speech recognition (Chrome / Edge). Returns null where unsupported. */
type Recognition = {
  lang: string; interimResults: boolean; continuous: boolean;
  onresult: (e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void;
  onend: () => void; onerror: (e: { error: string }) => void; start: () => void; stop: () => void;
};

export function createRecognition(): Recognition | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
  const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
  if (!Ctor) return null;
  const r = new Ctor();
  // Indian English: understands Indian accents and writes Hinglish in Roman script ("kal mera lecture kab hai"),
  // which is what the assistant mirrors back.
  r.lang = "en-IN";
  r.interimResults = true;
  r.continuous = false; // stops by itself after a pause, then the question is sent
  return r;
}

/** Plain-language reason for a speech-recognition error (null = nothing worth showing). */
export function voiceErrorText(code: string): string | null {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "The microphone is blocked. Allow it from the icon at the left of the address bar, then tap the mic again.";
    case "audio-capture":
      return "No microphone found. Plug one in or type your question.";
    case "no-speech":
      return "I didn't hear anything. Tap the mic and speak, or type your question.";
    case "network":
      return "Voice needs an internet connection. You can still type your question.";
    default:
      return null; // "aborted": the user stopped it
  }
}

/** Read a reply aloud (browser speech). Markdown marks are removed first. Returns false where unsupported. */
export function speak(text: string, onEnd: () => void): boolean {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
  const plain = text
    .replace(/\*\*/g, "")
    .replace(/^\s*[-*•]\s+/gm, "")
    .replace(/[`#_]/g, "")
    .replace(/(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})/g, "$1:$2 to $3:$4")
    .trim();
  if (!plain) return false;
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(plain);
  const voices = synth.getVoices();
  const voice = voices.find((v) => v.lang === "en-IN") ?? voices.find((v) => v.lang.startsWith("en"));
  if (voice) u.voice = voice;
  u.lang = voice?.lang ?? "en-IN";
  u.rate = 1.02;
  u.onend = onEnd;
  u.onerror = onEnd;
  synth.speak(u);
  return true;
}

export function stopSpeaking() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
}
