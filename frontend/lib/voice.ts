/**
 * Voice for the assistant: listening (microphone) and speaking (reading answers aloud).
 *
 * Listening: the microphone stays open through pauses. A level meter notices when the person starts and stops
 * talking. With cloud voice set up (OPENAI_API_KEY on the assistant service) the recording is transcribed there;
 * the browser's own recognition shows a live preview meanwhile, and is the transcript when there is no cloud voice.
 * Speaking: answers are read sentence by sentence while they stream in (cloud voice, else the browser's voice),
 * and stop the moment the person speaks over them.
 */
import { getSession } from "./api";
import { createRecognition } from "./chat";

const CHATBOT = process.env.NEXT_PUBLIC_CHATBOT_URL ?? "http://127.0.0.1:8001";

let cloud: Promise<boolean> | null = null;
/** Is cloud voice (better listening + natural voice) set up on the assistant service? */
export function cloudVoice(): Promise<boolean> {
  cloud ??= fetch(`${CHATBOT}/voice`).then((r) => r.json()).then((j) => !!j.cloud).catch(() => false);
  return cloud;
}

/** Spoken words that only stop the assistant talking; never sent as a question. */
export function isStopWord(text: string): boolean {
  return /^(stop|stop it|ok stop|ruko|ruk jao|bas|bas karo|chup|enough|wait|cancel|band karo)[\s.!]*$/i.test(text.trim());
}

/** Markdown and symbols out, times read naturally. */
export function plainForSpeech(text: string): string {
  return text
    .replace(/\*\*/g, "")
    .replace(/^\s*[-*•]\s+/gm, "")
    .replace(/[`#_|]/g, "")
    .replace(/(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})/g, "$1:$2 to $3:$4")
    .replace(/\s+/g, " ")
    .trim();
}

export function micErrorText(e: unknown): string {
  const name = e instanceof DOMException ? e.name : "";
  if (name === "NotAllowedError" || name === "SecurityError")
    return "The microphone is blocked. Allow it from the icon at the left of the address bar, then try again.";
  if (name === "NotFoundError") return "No microphone found. Plug one in or type your question.";
  return "The microphone didn't start. Type your question, or try again.";
}

// ---------------------------------------------------------------------------
// Listening
// ---------------------------------------------------------------------------

export interface UtteranceOptions {
  autoEnd: boolean; // talk mode: the utterance ends by itself after a pause
  onPreview?: (text: string) => void; // live words (browser recognition), while speaking
  onSpeech?: () => void; // the person started speaking (used to interrupt the answer being read)
  onAutoEnd?: () => void; // autoEnd: they finished speaking
}

const SILENCE_MS = 1000; // pause that ends a spoken question in talk mode
const START_MS = 180; // talking this long counts as speech (ignores clicks and coughs)

export class Mic {
  private stream: MediaStream | null = null;
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private recognition: ReturnType<typeof createRecognition> = null;
  private preview = "";
  private finals = "";
  private opts: UtteranceOptions | null = null;
  private noise = 0.01;
  private loudSince = 0;
  private lastVoice = 0;
  private started = false; // speech heard in this utterance
  private strict = false; // the answer is being read aloud: only clear speech interrupts it
  level = 0;

  constructor(private readonly useCloud: boolean, private readonly onLevel?: (level: number) => void) {}

  get open(): boolean {
    return this.stream !== null;
  }

  /** Ask for the microphone (once) and start the level meter. Throws a DOMException if blocked. */
  async start(): Promise<void> {
    if (this.stream) return;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.ctx = new Ctx();
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 1024;
    this.ctx.createMediaStreamSource(this.stream).connect(this.analyser);
    const buf = new Float32Array(new ArrayBuffer(this.analyser.fftSize * 4));
    this.timer = setInterval(() => this.tick(buf), 50);
  }

  /** Answer being read aloud: raise the bar so the speaker's own echo doesn't count as the person talking. */
  setStrict(on: boolean) {
    this.strict = on;
  }

  private tick(buf: Float32Array<ArrayBuffer>) {
    if (!this.analyser) return;
    this.analyser.getFloatTimeDomainData(buf);
    let sum = 0;
    for (const v of buf) sum += v * v;
    const rms = Math.sqrt(sum / buf.length);
    // Slowly track the room's background noise; speech must stand clearly above it.
    this.noise = rms < this.noise ? rms : this.noise * 0.995 + rms * 0.005;
    const bar = this.strict ? Math.max(0.06, this.noise * 6) : Math.max(0.018, this.noise * 3);
    const now = performance.now();
    this.level = Math.min(1, rms / 0.15);
    this.onLevel?.(this.level);
    if (!this.opts) return;
    if (rms > bar) {
      this.lastVoice = now;
      if (!this.loudSince) this.loudSince = now;
      if (!this.started && now - this.loudSince > (this.strict ? 350 : START_MS)) {
        this.started = true;
        this.opts.onSpeech?.();
      }
    } else if (now - this.lastVoice > 250) {
      this.loudSince = 0;
    }
    if (this.opts.autoEnd && this.started && now - this.lastVoice > SILENCE_MS) {
      const done = this.opts.onAutoEnd;
      this.opts = { ...this.opts, autoEnd: false }; // fire once
      done?.();
    }
  }

  /** Begin one spoken message: record it (cloud) and show live words (browser recognition). */
  beginUtterance(opts: UtteranceOptions) {
    if (!this.stream) return;
    this.endRecording();
    this.opts = opts;
    this.started = false;
    this.loudSince = 0;
    this.lastVoice = performance.now();
    this.preview = "";
    this.finals = "";
    this.chunks = [];
    if (this.useCloud && typeof MediaRecorder !== "undefined") {
      const type = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"].find((t) => MediaRecorder.isTypeSupported(t));
      this.recorder = new MediaRecorder(this.stream, type ? { mimeType: type } : undefined);
      this.recorder.ondataavailable = (e) => e.data.size && this.chunks.push(e.data);
      this.recorder.start(250);
    }
    this.startRecognition();
  }

  private startRecognition() {
    const r = createRecognition();
    if (!r) return;
    r.continuous = true; // a pause doesn't end it: the person decides when they are done
    r.onresult = (e) => {
      let finals = "";
      let interim = "";
      for (const res of Array.from(e.results)) {
        if (res.isFinal) finals += res[0].transcript + " ";
        else interim += res[0].transcript;
      }
      this.finals = finals;
      this.preview = (finals + interim).trim();
      this.opts?.onPreview?.(this.preview);
    };
    r.onerror = () => {};
    // Chrome ends recognition after a while: keep it going while the utterance lasts, keeping what was heard.
    r.onend = () => {
      if (this.recognition === r && this.opts) {
        const kept = this.preview;
        this.recognition = null;
        this.startRecognition();
        const next = this.recognition as ReturnType<typeof createRecognition>;
        if (next) {
          const orig = next.onresult;
          next.onresult = (e) => {
            orig(e);
            this.preview = `${kept} ${this.preview}`.trim();
            this.finals = `${kept} ${this.finals}`;
            this.opts?.onPreview?.(this.preview);
          };
        }
      }
    };
    this.recognition = r;
    try {
      r.start();
    } catch {
      this.recognition = null;
    }
  }

  private endRecording(): Promise<Blob | null> {
    const rec = this.recorder;
    this.recorder = null;
    const r = this.recognition;
    this.recognition = null;
    try {
      r?.stop();
    } catch {
      /* already stopped */
    }
    if (!rec || rec.state === "inactive") return Promise.resolve(null);
    return new Promise((resolve) => {
      rec.onstop = () => resolve(this.chunks.length ? new Blob(this.chunks, { type: rec.mimeType || "audio/webm" }) : null);
      rec.stop();
    });
  }

  /** End the current message and return its text ("" if nothing was said). */
  async finishUtterance(): Promise<string> {
    const heard = this.started;
    const fallback = (this.preview || this.finals).trim();
    this.opts = null;
    const blob = await this.endRecording();
    if (!blob || !heard) return fallback;
    try {
      const { token, org } = getSession();
      const res = await fetch(`${CHATBOT}/transcribe?org=${encodeURIComponent(org || "platform")}`, {
        method: "POST", body: blob, headers: { "Content-Type": blob.type, Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return fallback;
      const text = ((await res.json()) as { text?: string }).text?.trim();
      return text || fallback;
    } catch {
      return fallback;
    }
  }

  cancelUtterance() {
    this.opts = null;
    void this.endRecording();
  }

  /** Release the microphone. */
  stop() {
    this.cancelUtterance();
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    void this.ctx?.close().catch(() => {});
    this.ctx = null;
    this.analyser = null;
    this.level = 0;
    this.onLevel?.(0);
  }
}

// ---------------------------------------------------------------------------
// Speaking
// ---------------------------------------------------------------------------

// A sentence and its cloud audio player (null = the browser's voice). The player is created as soon as the
// sentence is known, so its audio is already arriving while the sentence before it plays.
type Clip = { text: string; audio: Promise<HTMLAudioElement | null> };
const CLOUD_WAIT_MS = 5000; // cloud voice slower than this to start -> that sentence uses the browser's voice

/** Reads an answer aloud while it streams in: complete sentences are spoken in order, the next one is fetched
 *  while the current one plays. ``stop()`` silences it at once. */
export class Speaker {
  private buffer = "";
  private queue: Clip[] = [];
  private playing = false;
  private ended = false;
  private current: HTMLAudioElement | null = null;
  private generation = 0;
  private aborts: AbortController[] = [];
  private players: HTMLAudioElement[] = [];

  constructor(private readonly useCloud: boolean, private readonly onState: (speaking: boolean) => void) {}

  get active(): boolean {
    return this.playing || this.queue.length > 0;
  }

  /** New answer: forget anything from the last one. */
  reset() {
    this.stop();
    this.ended = false;
  }

  /** More streamed answer text. */
  push(text: string) {
    this.buffer += text;
    for (;;) {
      const m = /([.!?।]+["')\]]?\s)|(\n+)/.exec(this.buffer.slice(30)); // sentences of at least ~30 characters
      if (!m) break;
      const cut = 30 + m.index + m[0].length;
      this.enqueue(this.buffer.slice(0, cut));
      this.buffer = this.buffer.slice(cut);
    }
  }

  /** The answer is complete: speak what is left. */
  end() {
    this.enqueue(this.buffer);
    this.buffer = "";
    this.ended = true;
    if (!this.active) this.onState(false);
  }

  /** Speak one whole text (e.g. an answer that was not streamed). */
  say(text: string) {
    this.reset();
    this.push(text);
    this.end();
  }

  private enqueue(raw: string) {
    const text = plainForSpeech(raw);
    if (!text) return;
    this.queue.push({ text, audio: this.fetchAudio(text) });
    if (!this.playing) void this.playNext(this.generation);
  }

  private fetchAudio(text: string): Promise<HTMLAudioElement | null> {
    if (!this.useCloud) return Promise.resolve(null);
    const ac = new AbortController();
    this.aborts.push(ac);
    const { token, org } = getSession();
    // Step 1 (with the login): hand over the text. Step 2: the player streams the audio by a one-time id and
    // starts playing while it is still arriving.
    return fetch(`${CHATBOT}/speak/start`, {
      method: "POST", signal: ac.signal,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ org: org || "platform", text }),
    }).then(async (r) => {
      if (!r.ok) return null;
      const { id } = (await r.json()) as { id: string };
      const a = new Audio(`${CHATBOT}/speak/${id}`);
      a.preload = "auto";
      a.load();
      this.players.push(a);
      return a;
    }).catch(() => null);
  }

  private async playNext(gen: number) {
    const clip = this.queue.shift();
    if (!clip || gen !== this.generation) {
      this.playing = false;
      if (gen === this.generation && this.ended) this.onState(false);
      return;
    }
    this.playing = true;
    this.onState(true);
    const player = await clip.audio;
    if (gen !== this.generation) return;
    await (player ? this.playCloud(player, clip.text) : this.playBrowser(clip.text));
    if (gen !== this.generation) return;
    void this.playNext(gen);
  }

  private playCloud(a: HTMLAudioElement, text: string): Promise<void> {
    return new Promise((resolve) => {
      this.current = a;
      let started = false;
      let settled = false;
      const finish = (useBrowser: boolean) => {
        if (settled) return;
        settled = true;
        clearTimeout(slow);
        if (useBrowser) {
          a.pause();
          a.removeAttribute("src");
          this.current = null;
          void this.playBrowser(text).then(resolve);
        } else resolve();
      };
      const slow = setTimeout(() => !started && finish(true), CLOUD_WAIT_MS);
      a.onplaying = () => { started = true; clearTimeout(slow); };
      a.onended = () => finish(false);
      a.onerror = () => finish(!started);
      a.play().catch(() => finish(!started));
    });
  }

  private playBrowser(text: string): Promise<void> {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return Promise.resolve();
    return new Promise((resolve) => {
      const synth = window.speechSynthesis;
      const u = new SpeechSynthesisUtterance(text);
      const voices = synth.getVoices();
      const voice = voices.find((v) => v.lang === "en-IN") ?? voices.find((v) => v.lang.startsWith("en"));
      if (voice) u.voice = voice;
      u.lang = voice?.lang ?? "en-IN";
      u.rate = 1.05;
      u.onend = u.onerror = () => resolve();
      synth.speak(u);
    });
  }

  /** Silence now (the person spoke, said "stop", or pressed Stop). */
  stop() {
    this.generation++;
    this.queue = [];
    this.buffer = "";
    this.aborts.forEach((a) => a.abort());
    this.aborts = [];
    this.players.forEach((a) => { a.pause(); a.removeAttribute("src"); });
    this.players = [];
    this.current?.pause();
    this.current = null;
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    this.playing = false;
    this.ended = true;
    this.onState(false);
  }
}
