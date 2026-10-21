"use client";

import { createContext, useContext, useMemo, useState } from "react";
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
}

const Ctx = createContext<ChatPageState | null>(null);

export function ChatPageProvider({ children }: { children: React.ReactNode }) {
  const [page, setPage] = useState<Omit<PageInfo, "path">>({});
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const value = useMemo(
    () => ({
      page, setPage, open, setOpen, pending,
      ask: (q: string) => {
        setPending(q);
        setOpen(true);
      },
      clearPending: () => setPending(null),
    }),
    [page, open, pending],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useChatPage(): ChatPageState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useChatPage must be used inside ChatPageProvider");
  return v;
}
