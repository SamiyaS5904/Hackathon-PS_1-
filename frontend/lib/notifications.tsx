"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { useTimetable } from "./timetable-context";
import type { Notification } from "./types";

const POLL_MS = 30_000;

interface NotificationState {
  items: Notification[] | null;
  unread: number;
  failed: boolean;
  /** Opening the panel: the server marks everything seen; items keep their "new" dot until it closes. */
  markSeen: () => void;
  clearDots: () => void;
}

const Ctx = createContext<NotificationState | null>(null);

/** One feed for the whole app (both bells read it). Polls only while the tab is visible; new items also
 *  refresh the timetable, so what people see matches what they're told. */
export function NotificationsProvider({ children }: { children: React.ReactNode }) {
  const { reload } = useTimetable();
  const [items, setItems] = useState<Notification[] | null>(null);
  const [unread, setUnread] = useState(0);
  const [failed, setFailed] = useState(false);
  const last = useRef<number | null>(null);

  const load = useCallback(async () => {
    if (document.visibilityState === "hidden") return;
    try {
      const f = await api.notifications();
      setItems(f.items);
      setUnread(f.unread);
      setFailed(false);
      const newest = f.items[0]?.at ?? 0;
      if (last.current !== null && newest > last.current) void reload();
      last.current = newest;
    } catch {
      setFailed(true);
    }
  }, [reload]);

  useEffect(() => {
    void load();
    const id = setInterval(load, POLL_MS);
    const onShow = () => void load();
    window.addEventListener("focus", onShow);
    document.addEventListener("visibilitychange", onShow);
    return () => {
      clearInterval(id);
      window.removeEventListener("focus", onShow);
      document.removeEventListener("visibilitychange", onShow);
    };
  }, [load]);

  const value = useMemo<NotificationState>(() => ({
    items, unread, failed,
    markSeen: () => {
      if (unread === 0) return;
      setUnread(0);
      api.seenNotifications().catch(() => {});
    },
    clearDots: () => setItems((list) => list?.map((n) => ({ ...n, unread: false })) ?? null),
  }), [items, unread, failed]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useNotifications(): NotificationState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useNotifications must be used inside NotificationsProvider");
  return v;
}
