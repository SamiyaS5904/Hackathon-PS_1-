"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useTimetable } from "@/lib/timetable-context";
import { useToast } from "@/lib/toast";
import type { MoveOption, Proposal, Session } from "@/lib/types";
import type { EditState } from "./TimetableGrid";

export interface Toast {
  text: string;
  tone?: "ok" | "danger";
}

export interface MoveRequest {
  session: Session;
  option: MoveOption;
}

/** Move flow: pick a class -> see valid slots -> drop -> preview the repair -> apply / discard -> undo.
 *  ``requestOnly`` (teachers): dropping prepares a request for the Department Coordinator instead. */
export function useMoveEditor({ requestOnly = false }: { requestOnly?: boolean } = {}) {
  const { data, setData } = useTimetable();
  const [moving, setMoving] = useState<Session | null>(null);
  const [options, setOptions] = useState<Map<string, MoveOption> | null>(null);
  const [busy, setBusy] = useState(false);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [changedIds, setChangedIds] = useState<Set<string>>(new Set());
  const showToast = useToast();
  const setToast = useCallback((t: Toast) => showToast(t), [showToast]);
  const [moveRequest, setMoveRequest] = useState<MoveRequest | null>(null);

  const cancel = useCallback(() => {
    setMoving(null);
    setOptions(null);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !proposal && cancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cancel, proposal]);

  const pick = useCallback(
    async (s: Session) => {
      if (moving?.id === s.id) return cancel();
      setMoving(s);
      setOptions(null);
      try {
        const opts = await api.moveOptions(s.id);
        setOptions(new Map(opts.map((o) => [`${o.day}|${o.start}`, o])));
      } catch (e) {
        setToast({ text: e instanceof Error ? e.message : "Couldn't load options", tone: "danger" });
        cancel();
      }
    },
    [moving, cancel, setToast],
  );

  const drop = useCallback(
    async (day: string, start: string) => {
      if (!moving || !options) return;
      const opt = options.get(`${day}|${start}`);
      if (!opt || opt.status === "blocked") return;
      if (requestOnly) {
        setMoveRequest({ session: moving, option: opt });
        return;
      }
      setBusy(true);
      try {
        setProposal(await api.propose({ session_id: moving.id, day, start_period: opt.start_period }));
      } catch (e) {
        setToast({ text: e instanceof Error ? e.message : "That move isn't possible", tone: "danger" });
      } finally {
        setBusy(false);
      }
    },
    [moving, options, requestOnly, setToast],
  );

  const apply = useCallback(async () => {
    if (!proposal) return;
    setBusy(true);
    try {
      const out = await api.apply(proposal.id);
      setData(out);
      setChangedIds(new Set(proposal.changes.map((c) => c.session_id)));
      showToast({
        text: proposal.message, undoEntryId: out.last_change?.id,
        onUndone: (o) => { setData(o); setChangedIds(new Set()); },
      });
      setProposal(null);
      cancel();
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : "Couldn't apply the change", tone: "danger" });
      setProposal(null);
    } finally {
      setBusy(false);
    }
  }, [proposal, setData, cancel, setToast, showToast]);

  const sendRequest = useCallback(
    async (reason: string) => {
      if (!moveRequest) return;
      setBusy(true);
      try {
        await api.requestChange({
          session_id: moveRequest.session.id, day: moveRequest.option.day,
          start_period: moveRequest.option.start_period, reason,
        });
        setToast({ text: "Sent to your Department Coordinator. You'll get a notification when they decide.", tone: "ok" });
        setMoveRequest(null);
        cancel();
      } catch (e) {
        setToast({ text: e instanceof Error ? e.message : "Couldn't send the request", tone: "danger" });
      } finally {
        setBusy(false);
      }
    },
    [moveRequest, cancel, setToast],
  );

  const discard = useCallback(() => {
    if (proposal) api.discard(proposal.id);
    setProposal(null);
  }, [proposal]);

  const edit: EditState | undefined = data
    ? { movingId: moving?.id ?? null, options, busy, changedIds, onPick: pick, onDrop: drop }
    : undefined;

  return {
    edit, moving, options, busy, proposal, apply, discard, cancel, setToast,
    moveRequest, sendRequest, closeRequest: () => setMoveRequest(null),
  };
}
