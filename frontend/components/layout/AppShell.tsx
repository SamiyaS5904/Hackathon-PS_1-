"use client";

import clsx from "clsx";
import { CalendarDays, Database, LayoutDashboard, Loader2 } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { isGenerating, useTimetable } from "@/lib/timetable-context";

// Core-first order (root CLAUDE.md §2A). Secondary items go below a divider once they exist.
const CORE = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/timetable", label: "Timetable", icon: CalendarDays },
  { href: "/data", label: "College data", icon: Database },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { college, job } = useTimetable();

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-surface px-3 py-5 md:flex">
        <Link href="/" className="mb-6 flex items-center gap-2 px-2">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-accent text-sm font-bold text-white dark:text-bg">
            T
          </span>
          <span className="font-semibold tracking-tight">Timetabl.ai</span>
        </Link>

        <div className="mb-4 rounded-lg border border-border bg-surface-2 px-3 py-2">
          <p className="text-[11px] uppercase tracking-wide text-muted">College</p>
          <p className="truncate text-sm font-medium">{college?.name ?? "Loading…"}</p>
        </div>

        <nav className="flex flex-col gap-0.5">
          {CORE.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? path === "/" : path.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={clsx(
                  "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition",
                  active ? "bg-accent-soft font-medium text-accent-text" : "text-muted hover:bg-surface-2 hover:text-text",
                )}
              >
                <Icon size={16} aria-hidden />
                {label}
              </Link>
            );
          })}
        </nav>

        {isGenerating(job) && (
          <div className="mt-auto flex items-center gap-2 rounded-lg bg-accent-soft px-3 py-2 text-xs text-accent-text">
            <Loader2 size={14} className="animate-spin" aria-hidden />
            Generating timetable… {job?.elapsed.toFixed(0)}s
          </div>
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-border bg-surface px-4 py-3 md:hidden">
          <span className="font-semibold">Timetabl.ai</span>
          <nav className="ml-auto flex gap-1">
            {CORE.map(({ href, label }) => (
              <Link key={href} href={href} className="rounded px-2 py-1 text-sm text-muted hover:bg-surface-2">
                {label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="flex-1 px-4 py-6 md:px-8">{children}</main>
      </div>
    </div>
  );
}
