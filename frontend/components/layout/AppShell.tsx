"use client";

import clsx from "clsx";
import { Building2, CalendarCheck, CalendarClock, CalendarDays, ChevronDown, ClipboardCheck, Database, GitCompareArrows, Home, ListChecks, Loader2, LogOut, MoreHorizontal, Settings2, Sparkles, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ROLE_LABEL, useAuth } from "@/lib/auth";
import { useChatPage } from "@/lib/chat-context";
import { ThemeToggle } from "@/lib/theme";
import { isGenerating, useTimetable } from "@/lib/timetable-context";
import type { Role } from "@/lib/types";
import { NotificationBell } from "./NotificationBell";

type Item = { href: string; label: string; icon: typeof Home; roles: Role[] };

// Core first (root CLAUDE.md §2A): the main items are the daily core actions; everything else sits under "More".
// Bookings is a main item for teachers and students: it is how they meet outside class.
const CORE: Item[] = [
  { href: "/", label: "Home", icon: Home, roles: ["admin", "coordinator", "teacher", "student"] },
  { href: "/timetable", label: "Timetable", icon: CalendarDays, roles: ["admin", "coordinator"] },
  { href: "/timetable", label: "My timetable", icon: CalendarDays, roles: ["teacher", "student"] },
  { href: "/setup", label: "Setup", icon: Settings2, roles: ["admin"] },
  { href: "/departments", label: "My department", icon: Building2, roles: ["coordinator"] },
  { href: "/changes", label: "Changes", icon: GitCompareArrows, roles: ["admin", "coordinator", "teacher", "student"] },
  { href: "/bookings", label: "Bookings", icon: CalendarCheck, roles: ["teacher", "student"] },
];
const MORE: Item[] = [
  { href: "/departments", label: "Departments", icon: Building2, roles: ["admin"] },
  { href: "/attendance", label: "Attendance", icon: ClipboardCheck, roles: ["admin", "coordinator", "teacher"] },
  { href: "/attendance", label: "My attendance", icon: ClipboardCheck, roles: ["student"] },
  { href: "/bookings", label: "Meetings", icon: CalendarCheck, roles: ["admin", "coordinator"] },
  { href: "/availability", label: "My availability", icon: CalendarClock, roles: ["teacher"] },
  { href: "/rules", label: "Rules", icon: ListChecks, roles: ["admin", "coordinator"] },
  { href: "/data", label: "College data", icon: Database, roles: ["admin", "coordinator"] },
  { href: "/members", label: "People & invites", icon: Users, roles: ["admin", "coordinator"] },
];
const MORE_KEY = "tt-nav-more";

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { college, job } = useTimetable();
  const { user, member, role, signOut } = useAuth();
  const { setOpen: openAssistant } = useChatPage();
  const core = CORE.filter((i) => role && i.roles.includes(role));
  const more = MORE.filter((i) => role && i.roles.includes(role));
  const inMore = more.some((i) => path.startsWith(i.href));
  const [moreOpen, setMoreOpen] = useState(false);
  const [mobileMore, setMobileMore] = useState(false);
  const mobileRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    try {
      setMoreOpen(localStorage.getItem(MORE_KEY) === "1");
    } catch {
      /* storage blocked: start closed */
    }
  }, []);
  useEffect(() => setMobileMore(false), [path]);
  useEffect(() => {
    if (!mobileMore) return;
    const close = (e: MouseEvent) => { if (!mobileRef.current?.contains(e.target as Node)) setMobileMore(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [mobileMore]);
  const toggleMore = () => {
    const next = !moreOpen;
    setMoreOpen(next);
    try {
      localStorage.setItem(MORE_KEY, next ? "1" : "0");
    } catch {
      /* keep for this visit */
    }
  };
  const showMore = moreOpen || inMore;

  const link = ({ href, label, icon: Icon }: Item) => {
    const active = href === "/" ? path === "/" : path.startsWith(href);
    return (
      <Link key={label} href={href}
        aria-current={active ? "page" : undefined}
        className={clsx("relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition",
          active ? "bg-accent-soft font-medium text-accent-text before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-full before:bg-accent"
            : "text-muted hover:bg-surface-2 hover:text-text")}>
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

        <div className="mb-5 rounded-lg border border-border bg-surface-2/70 px-3 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">College</p>
          <p className="truncate text-sm font-medium">{college?.name ?? member?.org_name ?? "Loading…"}</p>
        </div>

        <nav className="flex flex-col gap-0.5" aria-label="Main">
          {core.map(link)}
          <button onClick={() => openAssistant(true)}
            className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm text-muted transition hover:bg-surface-2 hover:text-text">
            <Sparkles size={16} aria-hidden /> Assistant
            <kbd className="ml-auto rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px]">Ctrl K</kbd>
          </button>
          {more.length > 0 && (
            <>
              <button onClick={toggleMore} aria-expanded={showMore}
                className="mt-3 flex items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm text-muted transition hover:bg-surface-2 hover:text-text">
                <MoreHorizontal size={16} aria-hidden /> More
                <ChevronDown size={14} className={clsx("ml-auto transition", showMore && "rotate-180")} aria-hidden />
              </button>
              {showMore && <div className="ml-3 flex flex-col gap-0.5 border-l border-border pl-2">{more.map(link)}</div>}
            </>
          )}
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
          {/* Core actions in one row; everything else behind "More". */}
          <nav className="relative flex items-center gap-1 px-3 py-2" aria-label="Main">
            <div className="flex min-w-0 flex-1 gap-1 overflow-x-auto whitespace-nowrap">
              {core.map(({ href, label }) => {
                const active = href === "/" ? path === "/" : path.startsWith(href);
                return (
                  <Link key={label} href={href}
                    className={clsx("shrink-0 rounded-md px-2.5 py-1 text-sm", active ? "bg-accent-soft font-medium text-accent-text" : "text-muted hover:bg-surface-2")}>
                    {label}
                  </Link>
                );
              })}
            </div>
            {more.length > 0 && (
              <div ref={mobileRef} className="shrink-0">
                <button onClick={() => setMobileMore(!mobileMore)} aria-expanded={mobileMore}
                  className={clsx("flex items-center gap-1 rounded-md px-2.5 py-1 text-sm", inMore ? "bg-accent-soft font-medium text-accent-text" : "text-muted hover:bg-surface-2")}>
                  More <ChevronDown size={14} aria-hidden />
                </button>
                {mobileMore && (
                  <div className="absolute right-3 top-full z-30 mt-1 w-52 rounded-xl border border-border bg-surface p-1.5 shadow-xl">
                    {more.map(({ href, label, icon: Icon }) => (
                      <Link key={label} href={href} className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm hover:bg-surface-2">
                        <Icon size={15} className="text-muted" aria-hidden /> {label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            )}
          </nav>
        </header>
        <main className="flex-1 px-4 py-6 md:px-8">{children}</main>
      </div>
    </div>
  );
}
