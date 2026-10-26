"use client";

import { Loader2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Field, FormError } from "@/components/Field";
import { Button, Skeleton } from "@/components/ui";
import { auth } from "@/lib/api";
import { ROLE_LABEL, useAuth } from "@/lib/auth";
import type { InviteOut } from "@/lib/types";
import Link from "next/link";

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const { signIn } = useAuth();
  const [invite, setInvite] = useState<InviteOut | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    auth.invite(token).then(setInvite).catch((e) => setLoadError(e instanceof Error ? e.message : "Invalid link"));
  }, [token]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) return setError("Enter a password.");
    setBusy(true);
    setError(null);
    try {
      signIn(await auth.accept(token, name, password));
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't accept the invite");
    } finally {
      setBusy(false);
    }
  };

  if (loadError) {
    return (
      <>
        <h1 className="text-lg font-semibold">Invite link not valid</h1>
        <p className="mt-2 text-sm text-muted">{loadError} Ask your College Admin for a new link.</p>
        <Link href="/login" className="mt-4 inline-block text-sm text-accent-text hover:underline">Go to log in</Link>
      </>
    );
  }
  if (!invite) return <Skeleton className="h-48 w-full" />;

  return (
    <>
      <h1 className="text-lg font-semibold">Join {invite.org_name}</h1>
      <p className="mt-1 text-sm text-muted">
        You&apos;re invited as <b className="text-text">{ROLE_LABEL[invite.role]}</b> ({invite.email}).
      </p>
      <form className="mt-5 space-y-3" onSubmit={submit}>
        <Field label="Your name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
        <Field label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password" hint="New here? Choose at least 8 characters. Already have an account? Use its password." />
        <FormError message={error} />
        <Button variant="primary" type="submit" className="w-full" disabled={busy}>
          {busy && <Loader2 size={16} className="animate-spin" />} Join college
        </Button>
      </form>
    </>
  );
}
