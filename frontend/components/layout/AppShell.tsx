"use client";

import clsx from "clsx";
import { Building2, CalendarClock, CalendarDays, ClipboardCheck, Database, History, Inbox, LayoutDashboard, ListChecks, Loader2, LogOut, Settings2, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ROLE_LABEL, useAuth } from "@/lib/auth";
import { ThemeToggle } from "@/lib/theme";
import { isGenerating, useTimetable } from "@/lib/timetable-context";
import type { Role } from "@/lib/types";
import { NotificationBell } from "./NotificationBell";

type Item = { href: string; label: string; icon: typeof LayoutDashboard; roles: Role[] };

// Core-first order (root CLAUDE.md §2A). Secondary items sit below a divider. Each role sees only its items.
const CORE: Item[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "coordinator"] },
  { href: "/timetable", label: "Timetable", icon: CalendarDays, roles: ["admin", "coordinator"] },
  { href: "/timetable", label: "My timetable", icon: CalendarDays, roles: ["teacher", "student"] },
  { href: "/setup", label: "College setup", icon: Settings2, roles: ["admin"] },
  { href: "/departments", label: "Departments", icon: Building2, roles: ["admin"] },
  { href: "/departments", label: "My department", icon: Building2, roles: ["coordinator"] },
  { href: "/attendance", label: "Attendance", icon: ClipboardCheck, roles: ["teacher"] },
  { href: "/attendance", label: "My attendance", icon: ClipboardCheck, roles: ["student"] },
  { href: "/availability", label: "My availability", icon: CalendarClock, roles: ["teacher"] },
];
const SECONDARY: Item[] = [
  { href: "/requests", label: "Change requests", icon: Inbox, roles: ["admin", "coordinator"] },
  { href: "/requests", label: "My requests", icon: Inbox, roles: ["teacher"] },
  { href: "/attendance", label: "Attendance", icon: ClipboardCheck, roles: ["admin", "coordinator"] },
  { href: "/rules", label: "Rules", icon: ListChecks, roles: ["admin", "coordinator"] },
  { href: "/data", label: "College data", icon: Database, roles: ["admin", "coordinator"] },
  { href: "/members", label: "People & invites", icon: Users, roles: ["admin", "coordinator"] },
  { href: "/activity", label: "Activity", icon: History, roles: ["admin", "coordinator"] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { college, job } = useTimetable();
  const { user, member, role, signOut } = useAuth();
  const core = CORE.filter((i) => role && i.roles.includes(role));
  const secondary = SECONDARY.filter((i) => role && i.roles.includes(role));

  const link = ({ href, label, icon: Icon }: Item) => {
    const active = href === "/" ? path === "/" : path.startsWith(href);
    return (
      <Link key={label} href={href}
        className={clsx("flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition",
          active ? "bg-accent-soft font-medium text-accent-text" : "text-muted hover:bg-surface-2 hover:text-text")}>
        <Icon size={16} aria-hidden />
        {label}
      </Link>
    );
  };

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-surface px-3 py-5 md:flex">
        <div className="mb-6 flex items-center gap-2 px-2">
          <Link href="/" className="flex flex-1 items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-accent text-sm font-bold text-white dark:text-bg">T</span>
            <span className="font-semibold tracking-tight">Timetabl.ai</span>
          </Link>
          <ThemeToggle />
          <NotificationBell />
        </div>

        <div className="mb-4 rounded-lg border border-border bg-surface-2 px-3 py-2">
          <p className="text-[11px] uppercase tracking-wide text-muted">College</p>
          <p className="truncate text-sm font-medium">{college?.name ?? member?.org_name ?? "Loading…"}</p>
        </div>

        <nav className="flex flex-col gap-0.5">
          {core.map(link)}
          {secondary.length > 0 && <hr className="my-2 border-border" />}
          {secondary.map(link)}
        </nav>

        <div className="mt-auto space-y-3">
          {isGenerating(job) && (
            <div className="flex items-center gap-2 rounded-lg bg-accent-soft px-3 py-2 text-xs text-accent-text">
              <Loader2 size={14} className="animate-spin" aria-hidden />
              Generating timetable… {job?.elapsed.toFixed(0)}s
            </div>
          )}
          <div className="flex items-center gap-2 rounded-lg border border-border px-3 py-2">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent-text">
              {user?.name.split(" ").map((w) => w[0]).slice(0, 2).join("")}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{user?.name}</p>
              <p className="truncate text-xs text-muted">{role ? ROLE_LABEL[role] : ""}</p>
            </div>
            <button onClick={signOut} aria-label="Log out" title="Log out" className="rounded p-1.5 text-muted hover:bg-surface-2 hover:text-text">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-border bg-surface md:hidden">
          <div className="flex items-center gap-2 px-4 pt-3">
            <span className="font-semibold">Timetabl.ai</span>
            <span className="truncate text-xs text-muted">{user?.name}</span>
            <span className="ml-auto flex items-center"><ThemeToggle /><NotificationBell align="right" /></span>
            <button onClick={signOut} aria-label="Log out" className="rounded p-1.5 text-muted hover:bg-surface-2"><LogOut size={16} /></button>
          </div>
          {/* One scrollable row instead of wrapping on small screens. */}
          <nav className="flex gap-1 overflow-x-auto whitespace-nowrap px-3 py-2">
            {[...core, ...secondary].map(({ href, label }) => {
              const active = href === "/" ? path === "/" : path.startsWith(href);
              return (
                <Link key={label} href={href}
                  className={clsx("shrink-0 rounded-md px-2.5 py-1 text-sm", active ? "bg-accent-soft font-medium text-accent-text" : "text-muted hover:bg-surface-2")}>
                  {label}
                </Link>
              );
            })}
          </nav>
        </header>
        <main className="flex-1 px-4 py-6 md:px-8">{children}</main>
      </div>
    </div>
  );
}
