"use client";

import { ArrowRight, CheckCircle2, Circle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge, Card, ErrorCard, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { DepartmentReadiness } from "@/lib/types";

export default function DepartmentsPage() {
  const { role, member } = useAuth();
  const router = useRouter();
  const [rows, setRows] = useState<DepartmentReadiness[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (role === "coordinator" && member?.department_id) router.replace(`/departments/${member.department_id}`);
  }, [role, member, router]);
  useEffect(() => {
    api.readiness().then(setRows).catch((e) => setError(e instanceof Error ? e.message : "Couldn't load"));
  }, []);

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Departments" subtitle="Each Coordinator fills in their department and marks it Ready. Generate once all are Ready." />
      {error && <ErrorCard message={error} />}
      {!rows ? (
        <Skeleton className="h-64 w-full" />
      ) : rows.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted">
          No departments yet. <Link href="/setup" className="text-accent-text hover:underline">Add them in the college setup</Link>.
        </Card>
      ) : (
        <Card className="divide-y divide-border">
          {rows.map((d) => (
            <Link key={d.department_id} href={`/departments/${d.department_id}`}
              className="flex items-center gap-4 px-5 py-4 transition hover:bg-surface-2">
              {d.ready ? <CheckCircle2 className="text-ok" size={20} /> : <Circle className="text-muted" size={20} />}
              <div className="min-w-0 flex-1">
                <p className="font-medium">{d.name}</p>
                <p className="text-xs text-muted">
                  {d.sections} sections · {d.teachers} teachers · {d.classes} classes · {d.students} students
                  {d.without_teacher > 0 && <span className="text-warn"> · {d.without_teacher} without a teacher</span>}
                </p>
              </div>
              {d.ready ? <Badge tone="ok">Ready{d.by ? ` · ${d.by}` : ""}</Badge> : <Badge>Not ready</Badge>}
              <ArrowRight size={16} className="text-muted" />
            </Link>
          ))}
        </Card>
      )}
    </div>
  );
}
