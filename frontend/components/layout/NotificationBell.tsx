"use client";

import clsx from "clsx";
import { Bell } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useNotifications } from "@/lib/notifications";

function ago(at: number): string {
  const s = Math.max(0, Date.now() / 1000 - at);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(at * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** Secondary: the bell. The feed itself lives in NotificationsProvider (one poll for the whole app). */
export function NotificationBell({ align = "left" }: { align?: "left" | "right" }) {
  const router = useRouter();
  const { items, unread, failed, markSeen, clearDots } = useNotifications();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) markSeen();
    else clearDots();
  };

  return (
    <div className="relative" ref={box}>
      <button
        type="button"
        onClick={toggle}
        aria-label={unread ? `Notifications, ${unread} new` : "Notifications"}
        aria-expanded={open}
        className="relative rounded-md p-1.5 text-muted hover:bg-surface-2 hover:text-text"
      >
        <Bell size={18} aria-hidden />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-danger px-1 text-[10px] font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div
          className={clsx(
            "absolute top-full z-40 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-border bg-surface shadow-xl",
            align === "left" ? "left-0" : "right-0",
          )}
          role="dialog"
          aria-label="Notifications"
        >
          <p className="border-b border-border px-4 py-2.5 text-sm font-semibold">Notifications</p>
          <ul className="max-h-96 overflow-auto">
            {failed && !items && <li className="px-4 py-6 text-center text-sm text-muted">Couldn&apos;t load notifications.</li>}
            {items && items.length === 0 && (
              <li className="px-4 py-6 text-center text-sm text-muted">
                Nothing yet. You&apos;ll hear here when the timetable is published or one of your classes changes.
              </li>
            )}
            {items?.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    router.push(n.link);
                  }}
                  className="flex w-full gap-2 px-4 py-3 text-left hover:bg-surface-2"
                >
                  <span className={clsx("mt-1.5 h-2 w-2 shrink-0 rounded-full", n.unread ? "bg-accent" : "bg-transparent")}
                    aria-label={n.unread ? "New" : undefined} />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{n.title}</span>
                    {n.body && <span className="mt-0.5 block text-xs text-muted">{n.body}</span>}
                    <span className="mt-1 block text-[11px] text-muted">{ago(n.at)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
