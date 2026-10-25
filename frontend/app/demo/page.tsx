"use client";

import { ArrowLeft, Globe2, GraduationCap, Loader2, School, User, UserCog } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { FormError } from "@/components/Field";
import { auth } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const PASSWORD = "demo1234";
const DOMAIN = "demo.timetabl.ai";
const DEPARTMENTS = [
  { id: "cse", name: "Computer Science" },
  { id: "ece", name: "Electronics" },
  { id: "me", name: "Mechanical" },
  { id: "as", name: "Applied Sciences" },
];
const SECTIONS = ["cse-1a", "cse-1b", "cse-2a", "cse-2b", "cse-3a", "cse-3b", "ece-1a", "ece-2a", "ece-3a",
  "me-1a", "me-2a", "me-3a"];
const sectionName = (id: string) => id.toUpperCase().replace(/-(\d)/, "-$1");

const select = "w-full rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";

/** Try the product as any role of the sample college: a click logs in, nothing to type. */
export default function DemoPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dept, setDept] = useState("cse");
  const [section, setSection] = useState("cse-3a");

  const go = async (email: string) => {
    setBusy(email);
    setError(null);
    try {
      const out = await auth.login(email, PASSWORD);
      signIn(out);
      router.replace(out.platform_owner && out.memberships.length === 0 ? "/platform" : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't open the demo");
    } finally {
      setBusy(null);
    }
  };

  const card = "flex w-full items-start gap-3 rounded-lg border border-border px-3 py-3 text-left text-sm transition hover:border-accent/40 hover:bg-accent-soft disabled:opacity-60";
  const icon = (email: string, Icon: typeof School) =>
    busy === email ? <Loader2 size={18} className="mt-0.5 animate-spin" aria-hidden />
      : <Icon size={18} className="mt-0.5 text-accent-text" aria-hidden />;

  const coordinator = `${dept}.coordinator@${DOMAIN}`;
  const student = `${section.replace("-", "")}.01@${DOMAIN}`;
  return (
    <>
      <Link href="/login" className="mb-4 inline-flex items-center gap-1 text-xs text-muted hover:text-text">
        <ArrowLeft size={14} aria-hidden /> Back to log in
      </Link>
      <h1 className="text-lg font-semibold">Try the demo college</h1>
      <p className="mt-1 text-sm text-muted">
        Demo Institute of Technology: 4 departments, 12 sections, 40 teachers. Pick who you want to be.
      </p>

      <div className="mt-5 space-y-2">
        <button className={card} disabled={!!busy} onClick={() => go(`admin@${DOMAIN}`)}>
          {icon(`admin@${DOMAIN}`, School)}
          <span>
            <span className="block font-medium">College Admin</span>
            <span className="text-xs text-muted">Set up the college, generate, publish, change anything</span>
          </span>
        </button>

        <div className={`${card} hover:bg-transparent`}>
          {icon(coordinator, UserCog)}
          <span className="flex-1 space-y-2">
            <span className="block font-medium">Department Coordinator</span>
            <span className="block text-xs text-muted">Own department&apos;s data, allotment, Ready, approvals</span>
            <span className="flex gap-2">
              <select className={select} value={dept} onChange={(e) => setDept(e.target.value)} aria-label="Department">
                {DEPARTMENTS.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              <button className="shrink-0 rounded-lg bg-accent px-3 text-sm font-medium text-white disabled:opacity-60 dark:text-bg"
                disabled={!!busy} onClick={() => go(coordinator)}>Open</button>
            </span>
          </span>
        </div>

        <button className={card} disabled={!!busy} onClick={() => go(`anita.sharma@${DOMAIN}`)}>
          {icon(`anita.sharma@${DOMAIN}`, User)}
          <span>
            <span className="block font-medium">Teacher: Dr. Anita Sharma</span>
            <span className="text-xs text-muted">Own lectures, one-day changes, requests, availability</span>
          </span>
        </button>

        <div className={`${card} hover:bg-transparent`}>
          {icon(student, GraduationCap)}
          <span className="flex-1 space-y-2">
            <span className="block font-medium">Student</span>
            <span className="block text-xs text-muted">Own section&apos;s week and the assistant</span>
            <span className="flex gap-2">
              <select className={select} value={section} onChange={(e) => setSection(e.target.value)} aria-label="Section">
                {SECTIONS.map((s) => <option key={s} value={s}>{sectionName(s)}, roll 01</option>)}
              </select>
              <button className="shrink-0 rounded-lg bg-accent px-3 text-sm font-medium text-white disabled:opacity-60 dark:text-bg"
                disabled={!!busy} onClick={() => go(student)}>Open</button>
            </span>
          </span>
        </div>

        <p className="pt-2 text-xs font-medium uppercase tracking-wide text-muted">For the Timetabl.ai team</p>
        <button className={card} disabled={!!busy} onClick={() => go(`owner@${DOMAIN}`)}>
          {icon(`owner@${DOMAIN}`, Globe2)}
          <span>
            <span className="block font-medium">Platform owner (SaaS)</span>
            <span className="text-xs text-muted">Every college on the platform: plans, progress, health, pause / read-only</span>
          </span>
        </button>
      </div>
      <div className="mt-3"><FormError message={error} /></div>
      <p className="mt-4 text-xs text-muted">
        Every demo account uses the password <code className="font-mono">{PASSWORD}</code>, so you can also log in by hand.
      </p>
    </>
  );
}
