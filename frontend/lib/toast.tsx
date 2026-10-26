"use client";

import clsx from "clsx";
import { Loader2, Undo2, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { TimetableOut } from "./types";

/** One message at the bottom of the screen. After a change is applied it offers Undo for 10 seconds;
 *  Undo targets exactly that change (the server refuses if something changed after it). */
export interface ToastInput {
  text: string;
  tone?: "ok" | "danger";
  undoEntryId?: string | null; // the change to undo (TimetableOut.last_change.id)
  onUndone?: (out: TimetableOut) => void;
}

const UNDO_MS = 10_000;
const PLAIN_MS = 5_000;

const Ctx = createContext<((t: ToastInput) => void) | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<ToastInput | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback((t: ToastInput) => setToast(t), []);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (toast && !busy) timer.current = setTimeout(() => setToast(null), toast.undoEntryId ? UNDO_MS : PLAIN_MS);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [toast, busy]);

  const undo = async () => {
    if (!toast?.undoEntryId) return;
    const { undoEntryId, onUndone } = toast;
    setBusy(true);
    try {
      const out = await api.undo(undoEntryId);
      onUndone?.(out);
      setToast({ text: "Undone. The timetable is back to how it was, and everyone affected is told." });
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : "Couldn't undo that change.", tone: "danger" });
    } finally {
      setBusy(false);
    }
  };

  const value = useMemo(() => show, [show]);
  return (
    <Ctx.Provider value={value}>
      {children}
      {toast && (
        <div role="status" aria-live="polite"
          className={clsx("no-print fixed bottom-5 left-1/2 z-50 flex max-w-[calc(100vw-2rem)] -translate-x-1/2 items-center gap-3 rounded-lg px-4 py-3 text-sm shadow-lg",
            toast.tone === "danger" ? "bg-danger text-white" : "bg-text text-bg")}>
          <span className="min-w-0">{toast.text}</span>
          {toast.undoEntryId && (
            <button onClick={undo} disabled={busy}
              className="inline-flex shrink-0 items-center gap-1 font-semibold underline-offset-2 hover:underline disabled:opacity-60">
              {busy ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <Undo2 size={14} aria-hidden />} Undo
            </button>
          )}
          <button onClick={() => setToast(null)} aria-label="Dismiss" className="shrink-0 opacity-70 hover:opacity-100">
            <X size={14} />
          </button>
        </div>
      )}
    </Ctx.Provider>
  );
}

/** Show a toast. Outside the provider (e.g. public pages) it does nothing. */
export function useToast(): (t: ToastInput) => void {
  return useContext(Ctx) ?? noop;
}

function noop() {}
