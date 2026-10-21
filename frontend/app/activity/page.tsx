"use client";

import clsx from "clsx";
import { ArrowRight, Undo2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useTimetable } from "@/lib/timetable-context";
import type { AuditEntry } from "@/lib/types";

const SOURCE: Record<string, { label: string; tone: "neutral" | "accent" | "ok" | "warn" }> = {
  generate: { label: "Generated", tone: "accent" },
  drag: { label: "Manual edit", tone: "neutral" },
  chatbot: { label: "Assistant", tone: "accent" },
  teacher: { label: "Teacher", tone: "warn" },
  undo: { label: "Undo", tone: "neutral" },
};

export default function ActivityPage() {
  const { setData, data } = useTimetable();
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setEntries(await api.audit());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load activity");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, data]);

  const undo = async () => {
    setBusy(true);
    try {
      setData(await api.undo());
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nothing to undo");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Activity" subtitle="Every change to the timetable: who, what, when and how. The latest change can be undone." />
      {error && <Card className="mb-4 border-danger/30 bg-danger-soft p-4 text-sm text-danger">{error}</Card>}
      {!entries ? (
        <Skeleton className="h-64 w-full" />
      ) : entries.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted">No activity yet. Generate a timetable to get started.</Card>
      ) : (
        <ol className="relative space-y-3 border-l border-border pl-5">
          {entries.map((e) => {
            const src = SOURCE[e.source] ?? { label: e.source, tone: "neutral" as const };
            return (
              <li key={e.id} className="relative">
                <span className="absolute -left-[26px] top-4 h-2.5 w-2.5 rounded-full border-2 border-surface bg-accent" />
                <Card className={clsx("p-4", e.undone && "opacity-60")}>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={src.tone}>{src.label}</Badge>
                    <span className={clsx("text-sm font-medium", e.undone && "line-through")}>{e.action}</span>
                    {e.undone && <Badge>undone</Badge>}
                    <span className="ml-auto text-xs text-muted">
                      {e.actor} · {new Date(e.at * 1000).toLocaleString()}
                    </span>
                  </div>
                  {e.changes.length > 0 && (
                    <ul className="mt-3 space-y-1.5 text-xs">
                      {e.changes.map((c) => (
                        <li key={c.session_id} className="flex flex-wrap items-center gap-2 text-muted">
                          <span className="font-medium text-text">{c.subject}</span>
                          <span>{c.sections}</span>
                          <span>{c.before}</span>
                          <ArrowRight size={12} aria-hidden />
                          <span className="text-text">{c.after}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {e.can_undo && (
                    <Button className="mt-3" onClick={undo} disabled={busy}>
                      <Undo2 size={14} aria-hidden /> Undo this change
                    </Button>
                  )}
                </Card>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
