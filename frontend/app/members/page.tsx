"use client";

import { Check, Copy, Loader2, UserPlus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Field, FormError } from "@/components/Field";
import { Badge, Button, Card, ErrorCard, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { ROLE_LABEL, useAuth } from "@/lib/auth";
import { useTimetable } from "@/lib/timetable-context";
import type { InviteOut, Member, Role } from "@/lib/types";

const inviteUrl = (token: string) => `${typeof window === "undefined" ? "" : window.location.origin}/invite/${token}`;

export default function MembersPage() {
  const { role, member } = useAuth();
  const { college } = useTimetable();
  const [people, setPeople] = useState<Member[] | null>(null);
  const [pending, setPending] = useState<InviteOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ email: "", role: "teacher" as Role, department_id: "", teacher_id: "" });
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [created, setCreated] = useState<InviteOut | null>(null);
  const [copied, setCopied] = useState("");

  const load = useCallback(async () => {
    try {
      const [m, i] = await Promise.all([api.members(), api.invites()]);
      setPeople(m);
      setPending(i);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load people");
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  // Coordinators invite teachers of their own department only.
  const roles: Role[] = role === "admin" ? ["coordinator", "teacher", "admin"] : ["teacher"];
  const departmentId = role === "coordinator" ? member?.department_id ?? "" : form.department_id;
  const deptTeachers = college?.teachers.filter((t) => t.department_id === departmentId) ?? [];
  const dept = new Map(college?.departments.map((d) => [d.id, d.short]) ?? []);

  const copy = async (token: string) => {
    try {
      await navigator.clipboard.writeText(inviteUrl(token));
      setCopied(token);
      setTimeout(() => setCopied(""), 2000);
    } catch {
      setCopied("");
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.email.trim()) return setFormError("Enter the email address.");
    if (form.role !== "admin" && !departmentId) return setFormError("Choose the department.");
    setBusy(true);
    setFormError(null);
    try {
      const inv = await api.invite({
        email: form.email, role: form.role,
        department_id: form.role === "admin" ? null : departmentId,
        teacher_id: form.role === "teacher" && form.teacher_id ? form.teacher_id : null,
      });
      setCreated(inv);
      setForm({ ...form, email: "", teacher_id: "" });
      load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Couldn't create the invite");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="People & invites" subtitle="Invite coordinators and teachers with a link. Students log in with their college email." />
      {error && <ErrorCard message={error} onRetry={load} />}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1.2fr] [&>*]:min-w-0">
        <Card className="p-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold"><UserPlus size={16} aria-hidden /> Invite someone</h2>
          <form className="mt-4 space-y-3" onSubmit={submit}>
            <Field label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="name@college.edu" />
            <label className="block text-sm">
              <span className="mb-1 block font-medium">Role</span>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}
                className="w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm">
                {roles.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
              </select>
            </label>
            {form.role !== "admin" && role === "admin" && (
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Department</span>
                <select value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value, teacher_id: "" })}
                  className="w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm">
                  <option value="">Choose…</option>
                  {college?.departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </label>
            )}
            {form.role === "teacher" && deptTeachers.length > 0 && (
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Link to teacher in the timetable <span className="font-normal text-muted">(optional)</span></span>
                <select value={form.teacher_id} onChange={(e) => setForm({ ...form, teacher_id: e.target.value })}
                  className="w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm">
                  <option value="">Not linked yet</option>
                  {deptTeachers.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
                <span className="mt-1 block text-xs text-muted">Linked teachers see and change their own lectures.</span>
              </label>
            )}
            <FormError message={formError} />
            <Button variant="primary" type="submit" disabled={busy}>
              {busy && <Loader2 size={16} className="animate-spin" />} Create invite link
            </Button>
          </form>

          {created && (
            <div className="mt-4 rounded-lg border border-ok/30 bg-ok-soft p-3 text-sm">
              <p className="font-medium text-ok">Invite ready for {created.email}</p>
              <p className="mt-1 text-xs text-muted">Send this link (WhatsApp, email…). It works once.</p>
              <div className="mt-2 flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded bg-surface px-2 py-1 font-mono text-xs">{inviteUrl(created.token)}</code>
                <Button onClick={() => copy(created.token)}>{copied === created.token ? <Check size={14} /> : <Copy size={14} />} Copy</Button>
              </div>
            </div>
          )}
        </Card>

        <div className="space-y-4">
          {pending.length > 0 && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold">Waiting to join ({pending.length})</h2>
              <ul className="mt-3 divide-y divide-border text-sm">
                {pending.map((i) => (
                  <li key={i.token} className="flex items-center justify-between gap-2 py-2">
                    <span className="min-w-0">
                      <span className="block truncate">{i.email}</span>
                      <span className="text-xs text-muted">{ROLE_LABEL[i.role]}{i.department_id ? ` · ${dept.get(i.department_id)}` : ""}</span>
                    </span>
                    <Button variant="ghost" onClick={() => copy(i.token)}>
                      {copied === i.token ? <Check size={14} /> : <Copy size={14} />} Link
                    </Button>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <Card className="overflow-hidden">
            <h2 className="border-b border-border px-5 py-3 text-sm font-semibold">
              Staff {people && <span className="font-normal text-muted">({people.length})</span>}
            </h2>
            {!people ? (
              <Skeleton className="m-5 h-40" />
            ) : (
              <ul className="max-h-[480px] divide-y divide-border overflow-auto text-sm">
                {people.map((p) => (
                  <li key={p.user_id} className="flex items-center justify-between gap-3 px-5 py-2.5">
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{p.name}</span>
                      <span className="block truncate text-xs text-muted">{p.email}</span>
                    </span>
                    <span className="flex shrink-0 items-center gap-1.5">
                      {p.department_id && <Badge>{dept.get(p.department_id) ?? p.department_id}</Badge>}
                      <Badge tone={p.role === "admin" ? "accent" : "neutral"}>{ROLE_LABEL[p.role]}</Badge>
                    </span>
                  </li>
                ))}
                {people.length <= 1 && (
                  <li className="px-5 py-4 text-sm text-muted">
                    Only you so far. Create an invite link on the left for each Department Coordinator and teacher: they
                    join with the role and department already set.
                  </li>
                )}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
