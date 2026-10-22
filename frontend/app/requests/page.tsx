"use client";

import { Check, Loader2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ProposalDialog } from "@/components/timetable/ProposalDialog";
import { Badge, Button, Card, ErrorCard, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { isStaff, useAuth } from "@/lib/auth";
import { useTimetable } from "@/lib/timetable-context";
import type { ChangeRequest, Proposal } from "@/lib/types";

const STATUS: Record<ChangeRequest["status"], { label: string; tone: "accent" | "ok" | "danger" | "neutral" }> = {
  pending: { label: "Waiting", tone: "accent" },
  approved: { label: "Approved", tone: "ok" },
  declined: { label: "Declined", tone: "danger" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
};

const when = (at: number) =>
  new Date(at * 1000).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Secondary page: teachers' requests for permanent moves. Coordinators review (fresh check + preview) and decide. */
export default function RequestsPage() {
  const { role } = useAuth();
  const { setData } = useTimetable();
  const reviewer = isStaff(role);
  const [items, setItems] = useState<ChangeRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [declining, setDeclining] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    try {
      setItems(await api.changeRequests());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load requests");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (id: string, fn: () => Promise<unknown>) => {
    setBusyId(id);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusyId(null);
    }
  };

  const review = (r: ChangeRequest) => run(r.id, async () => setProposal(await api.reviewRequest(r.id)));
  const apply = () =>
    proposal &&
    run("apply", async () => {
      setData(await api.apply(proposal.id));
      setProposal(null);
      await load();
    });
  const decline = (r: ChangeRequest) =>
    run(r.id, async () => {
      await api.declineRequest(r.id, note.trim());
      setDeclining(null);
      setNote("");
      await load();
    });
  const withdraw = (r: ChangeRequest) => run(r.id, async () => {
    await api.withdrawRequest(r.id);
    await load();
  });

  const pending = items?.filter((r) => r.status === "pending").length ?? 0;
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={reviewer ? "Change requests" : "My requests"}
        subtitle={reviewer
          ? "Teachers ask to move their lectures permanently. Review checks the move against today's timetable and shows exactly what changes."
          : "Your requests to move lectures permanently. Your Department Coordinator decides; you get a notification."}
      />
      {error && <div className="mb-4"><ErrorCard message={error} onRetry={load} /></div>}
      {!items ? (
        <Skeleton className="h-48 w-full" />
      ) : items.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted">
          {reviewer
            ? "No requests yet. When a teacher asks to move a lecture, it appears here and you get a notification."
            : "No requests yet. In My timetable, open Weekly plan, click one of your lectures and pick a new slot."}
        </Card>
      ) : (
        <>
          {reviewer && <p className="mb-3 text-sm text-muted">{pending} waiting for a decision.</p>}
          <ul className="space-y-3">
            {items.map((r) => (
              <li key={r.id}>
                <Card className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium">{r.summary.replace("->", "→")}</p>
                      <p className="mt-0.5 text-xs text-muted">
                        {reviewer ? `${r.teacher_name} · ` : ""}{when(r.at)}
                        {r.reason && <> · “{r.reason}”</>}
                      </p>
                      {r.status !== "pending" && r.decided_by && (
                        <p className="mt-1 text-xs text-muted">
                          {STATUS[r.status].label} by {r.decided_by}{r.decided_at ? `, ${when(r.decided_at)}` : ""}
                          {r.note && <> · “{r.note}”</>}
                        </p>
                      )}
                    </div>
                    <Badge tone={STATUS[r.status].tone}>{STATUS[r.status].label}</Badge>
                  </div>
                  {r.status === "pending" && reviewer && declining !== r.id && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button variant="primary" onClick={() => review(r)} disabled={busyId !== null}>
                        {busyId === r.id ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Check size={16} aria-hidden />}
                        Review and approve
                      </Button>
                      <Button onClick={() => setDeclining(r.id)} disabled={busyId !== null}>
                        <X size={16} aria-hidden /> Decline
                      </Button>
                    </div>
                  )}
                  {declining === r.id && (
                    <form className="mt-3 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); decline(r); }}>
                      <input autoFocus value={note} onChange={(e) => setNote(e.target.value)} maxLength={400}
                        placeholder="Note for the teacher (optional)" aria-label="Note for the teacher"
                        className="min-w-0 flex-1 rounded-lg border border-border bg-bg px-3 py-2 text-sm outline-none focus:border-accent" />
                      <Button type="button" onClick={() => setDeclining(null)}>Cancel</Button>
                      <Button type="submit" disabled={busyId !== null}>Decline request</Button>
                    </form>
                  )}
                  {r.status === "pending" && !reviewer && (
                    <div className="mt-3">
                      <Button variant="ghost" onClick={() => withdraw(r)} disabled={busyId !== null}>Withdraw</Button>
                    </div>
                  )}
                </Card>
              </li>
            ))}
          </ul>
        </>
      )}
      {proposal && (
        <ProposalDialog proposal={proposal} busy={busyId === "apply"} onApply={apply} onDiscard={() => {
          api.discard(proposal.id);
          setProposal(null);
        }} />
      )}
    </div>
  );
}
