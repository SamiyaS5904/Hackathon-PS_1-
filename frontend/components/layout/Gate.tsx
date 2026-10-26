"use client";

import { Loader2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { PUBLIC_PATHS, useAuth } from "@/lib/auth";
import { ChatPageProvider } from "@/lib/chat-context";
import { NotificationsProvider } from "@/lib/notifications";
import { TimetableProvider } from "@/lib/timetable-context";
import { ThemeToggle } from "@/lib/theme";
import { ToastProvider } from "@/lib/toast";
import { AppShell } from "./AppShell";
import { PlatformShell } from "./PlatformShell";
import Link from "next/link";

/** Public pages (login, signup, invite) render bare; everything else needs a login and a college. */
export function Gate({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { ready, user, member, signOut } = useAuth();
  const isPublic = PUBLIC_PATHS.some((p) => path.startsWith(p));
  const onPlatform = path.startsWith("/platform");
  // A platform owner without a college lands on the platform page.
  const toPlatform = ready && !!user?.platform_owner && !member && !onPlatform && !isPublic;
  useEffect(() => {
    if (toPlatform) router.replace("/platform");
  }, [toPlatform, router]);

  if (path.startsWith("/welcome")) return <>{children}</>; // the public home page has its own full-width layout
  if (isPublic) {
    return <AuthLayout>{children}</AuthLayout>;
  }
  if (ready && user && onPlatform) {
    if (!user.platform_owner) {
      return (
        <AuthLayout>
          <h1 className="text-lg font-semibold">Page not found</h1>
          <p className="mt-2 text-sm text-muted">This page is for the Timetabl.ai platform team.</p>
          <Link href="/" className="mt-4 inline-block text-sm text-accent-text hover:underline">Go to Home</Link>
        </AuthLayout>
      );
    }
    return (
      <ChatPageProvider>
        <PlatformShell>{children}</PlatformShell>
        <ChatPanel />
      </ChatPageProvider>
    );
  }
  if (!ready || !user || toPlatform) {
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
        <div className="mt-4 flex flex-wrap gap-2">
          <Link href="/signup" className="rounded-md bg-accent px-3.5 py-2 text-sm font-medium text-white dark:text-bg">Create a new college</Link>
          <button onClick={signOut} className="rounded-md border border-border-strong px-3.5 py-2 text-sm">Log out</button>
        </div>
      </AuthLayout>
    );
  }
  return (
    <TimetableProvider key={member.org_id}>
      <NotificationsProvider>
        <ChatPageProvider>
          <ToastProvider>
            <AppShell>{children}</AppShell>
            <ChatPanel />
          </ToastProvider>
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
        Clash-free college timetables for any college. Built by the algorithm, checked by an independent validator.{" "}
        <Link href="/welcome" className="text-accent-text hover:underline">What is Timetabl.ai?</Link>
      </p>
    </div>
  );
}
