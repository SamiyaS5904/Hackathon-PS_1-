"use client";

import { GraduationCap, Loader2, School, User, UserCog } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Field, FormError } from "@/components/Field";
import { Button } from "@/components/ui";
import { auth } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const DEMO = [
  { label: "College Admin", email: "admin@demo.timetabl.ai", icon: School, note: "Generate, edit, invite" },
  { label: "CSE Coordinator", email: "cse.coordinator@demo.timetabl.ai", icon: UserCog, note: "Own department" },
  { label: "Teacher", email: "anita.sharma@demo.timetabl.ai", icon: User, note: "Dr. Anita Sharma" },
  { label: "Student", email: "cse3a.01@demo.timetabl.ai", icon: GraduationCap, note: "CSE-3A, roll 01" },
];
const DEMO_PASSWORD = "demo1234";

export default function LoginPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const go = async (e: string, p: string, key: string) => {
    setBusy(key);
    setError(null);
    try {
      signIn(await auth.login(e, p));
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't log in");
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <h1 className="text-lg font-semibold">Log in</h1>
      <p className="mt-1 text-sm text-muted">Admins, coordinators, teachers and students all log in here.</p>
      <form
        className="mt-5 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!email.trim() || !password) return setError("Enter your email and password.");
          go(email, password, "form");
        }}
      >
        <Field label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)}
          placeholder="you@college.edu" />
        <Field label="Password" type="password" autoComplete="current-password" value={password}
          onChange={(e) => setPassword(e.target.value)} />
        <FormError message={error} />
        <Button variant="primary" type="submit" className="w-full" disabled={!!busy}>
          {busy === "form" && <Loader2 size={16} className="animate-spin" />} Log in
        </Button>
      </form>

      <div className="mt-6 border-t border-border pt-5">
        <p className="text-sm font-medium">Try the demo college</p>
        <p className="mb-3 text-xs text-muted">
          One click per role. Demo password: <code className="font-mono">{DEMO_PASSWORD}</code>. Every student has an
          email like <code className="font-mono">cse3a.01@demo.timetabl.ai</code>.
        </p>
        <div className="grid grid-cols-2 gap-2">
          {DEMO.map(({ label, email: e, icon: Icon, note }) => (
            <button key={e} onClick={() => go(e, DEMO_PASSWORD, e)} disabled={!!busy}
              aria-label={`Log in to the demo as ${label} (${note})`}
              className="flex items-start gap-2 rounded-lg border border-border px-3 py-2.5 text-left text-sm transition hover:border-accent/40 hover:bg-accent-soft disabled:opacity-60">
              {busy === e ? <Loader2 size={16} className="mt-0.5 animate-spin" /> : <Icon size={16} className="mt-0.5 text-accent-text" aria-hidden />}
              <span>
                <span className="block font-medium">{label}</span>
                <span className="text-xs text-muted">{note}</span>
              </span>
            </button>
          ))}
        </div>
      </div>

      <p className="mt-6 text-center text-sm text-muted">
        New college? <Link href="/signup" className="font-medium text-accent-text hover:underline">Create your workspace</Link>
      </p>
    </>
  );
}
