"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { PageInfo } from "./chat";

/** What the user is looking at, so "move this class" or "what's free here" make sense to the assistant. */
interface ChatPageState {
  page: Omit<PageInfo, "path">;
  setPage: (p: Omit<PageInfo, "path">) => void;
  open: boolean;
  setOpen: (o: boolean) => void;
  ask: (q: string) => void;
  pending: string | null;
  clearPending: () => void;
  // Open the assistant with a message typed in for the user to check and send.
  draft: string | null;
  prefill: (text: string) => void;
  clearDraft: () => void;
}

const Ctx = createContext<ChatPageState | null>(null);

export function ChatPageProvider({ children }: { children: React.ReactNode }) {
  const [page, setPage] = useState<Omit<PageInfo, "path">>({});
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const value = useMemo(
    () => ({
      page, setPage, open, setOpen, pending, draft,
      prefill: (text: string) => {
        setDraft(text);
        setOpen(true);
      },
      clearDraft: () => setDraft(null),
      ask: (q: string) => {
        setPending(q);
        setOpen(true);
      },
      clearPending: () => setPending(null),
    }),
    [page, open, pending, draft],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** A page tells the assistant which questions fit it. Cleared when the page closes. */
export function usePagePrompts(suggestions: string[]) {
  const { setPage } = useChatPage();
  const key = suggestions.join("|");
  useEffect(() => {
    setPage({ suggestions: key ? key.split("|") : [] });
    return () => setPage({});
  }, [key, setPage]);
}

export function useChatPage(): ChatPageState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useChatPage must be used inside ChatPageProvider");
  return v;
}
