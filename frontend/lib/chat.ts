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
  signal?: AbortSignal,
): Promise<void> {
  const { token, org } = getSession();
  const now = new Date();
  let res: Response;
  try {
    res = await fetch(`${CHATBOT}/chat`, {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        org, message, conversation_id: conversationId, page,
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
  r.lang = "en-IN";
  r.interimResults = true;
  r.continuous = false;
  return r;
}
