"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Field, FormError } from "@/components/Field";
import { Button } from "@/components/ui";
import { auth } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SignupPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [form, setForm] = useState({ name: "", email: "", password: "", college_name: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.email.trim() || !form.college_name.trim()) return setError("Fill in every field.");
    if (form.password.length < 8) return setError("Choose a password with at least 8 characters.");
    setBusy(true);
    setError(null);
    try {
      signIn(await auth.signup(form));
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the workspace");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1 className="text-lg font-semibold">Create your college workspace</h1>
      <p className="mt-1 text-sm text-muted">You&apos;ll be the College Admin. Invite coordinators and teachers next.</p>
      <form className="mt-5 space-y-3" onSubmit={submit}>
        <Field label="College name" value={form.college_name} onChange={set("college_name")}
          placeholder="e.g. Guru Nanak Dev Engineering College" />
        <Field label="Your name" value={form.name} onChange={set("name")} autoComplete="name" />
        <Field label="Work email" type="email" value={form.email} onChange={set("email")} autoComplete="email" />
        <Field label="Password" type="password" value={form.password} onChange={set("password")}
          autoComplete="new-password" hint="At least 8 characters." />
        <FormError message={error} />
        <Button variant="primary" type="submit" className="w-full" disabled={busy}>
          {busy && <Loader2 size={16} className="animate-spin" />} Create workspace
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        Already have an account? <Link href="/login" className="font-medium text-accent-text hover:underline">Log in</Link>
      </p>
    </>
  );
}
