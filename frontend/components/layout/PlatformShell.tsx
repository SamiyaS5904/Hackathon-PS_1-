"use client";

import { Building2, LogOut } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { ThemeToggle } from "@/lib/theme";

/** Layout for the platform owner (Super Admin): not inside any one college. */
export function PlatformShell({ children }: { children: React.ReactNode }) {
  const { user, signOut, switchOrg } = useAuth();
  const colleges = user?.memberships ?? [];
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-border bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
          <Link href="/platform" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-md bg-accent text-sm font-bold text-white dark:text-bg">T</span>
            <span className="font-semibold tracking-tight">Timetabl.ai</span>
            <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent-text">Platform</span>
          </Link>
          <div className="flex-1" />
          {colleges.length > 0 && (
            <Link href="/" onClick={() => switchOrg(colleges[0].org_id)}
              className="hidden items-center gap-1.5 rounded-md px-2 py-1 text-sm text-muted hover:bg-surface-2 sm:flex">
              <Building2 size={15} aria-hidden /> My college
            </Link>
          )}
          <ThemeToggle />
          <span className="hidden text-sm text-muted sm:inline">{user?.name}</span>
          <button onClick={signOut} aria-label="Log out" title="Log out" className="rounded p-1.5 text-muted hover:bg-surface-2 hover:text-text">
            <LogOut size={16} />
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
