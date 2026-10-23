"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Field, FormError } from "@/components/Field";
import { Button } from "@/components/ui";
import { auth } from "@/lib/api";
import { useAuth } from "@/lib/auth";

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

      <p className="mt-6 text-center text-sm text-muted">
        New college? <Link href="/signup" className="font-medium text-accent-text hover:underline">Create your workspace</Link>
      </p>
      <p className="mt-2 text-center text-xs text-muted">
        Just looking? <Link href="/demo" className="text-accent-text hover:underline">Try the demo college</Link>
      </p>
    </>
  );
}
