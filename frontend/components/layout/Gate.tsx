"use client";

import { Loader2 } from "lucide-react";
import { usePathname } from "next/navigation";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { PUBLIC_PATHS, useAuth } from "@/lib/auth";
import { ChatPageProvider } from "@/lib/chat-context";
import { NotificationsProvider } from "@/lib/notifications";
import { TimetableProvider } from "@/lib/timetable-context";
import { ThemeToggle } from "@/lib/theme";
import { AppShell } from "./AppShell";

/** Public pages (login, signup, invite) render bare; everything else needs a login and a college. */
export function Gate({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { ready, user, member } = useAuth();

  if (PUBLIC_PATHS.some((p) => path.startsWith(p))) {
    return <AuthLayout>{children}</AuthLayout>;
  }
  if (!ready || !user) {
    return (
      <div className="grid min-h-screen place-items-center text-sm text-muted">
        <Loader2 className="animate-spin" aria-label="Loading" />
      </div>
    );
  }
  if (!member) {
    return (
      <AuthLayout>
        <h1 className="text-lg font-semibold">No college yet</h1>
        <p className="mt-2 text-sm text-muted">
          Your account isn&apos;t part of any college. Ask your College Admin for an invite link, or create a new college.
        </p>
      </AuthLayout>
    );
  }
  return (
    <TimetableProvider key={member.org_id}>
      <NotificationsProvider>
        <ChatPageProvider>
          <AppShell>{children}</AppShell>
          <ChatPanel />
        </ChatPageProvider>
      </NotificationsProvider>
    </TimetableProvider>
  );
}

export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <ThemeToggle className="absolute right-4 top-4" />
      <div className="mb-6 flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-md bg-accent text-sm font-bold text-white dark:text-bg">T</span>
        <span className="text-lg font-semibold tracking-tight">Timetabl.ai</span>
      </div>
      <div className="w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-sm">{children}</div>
      <p className="mt-6 max-w-md text-center text-xs text-muted">
        Clash-free college timetables for any college. Built by the algorithm, checked by an independent validator.
      </p>
    </div>
  );
}
