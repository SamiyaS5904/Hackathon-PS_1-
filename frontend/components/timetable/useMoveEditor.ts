"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useTimetable } from "@/lib/timetable-context";
import type { MoveOption, Proposal, Session } from "@/lib/types";
import type { EditState } from "./TimetableGrid";

export interface Toast {
  text: string;
  undo?: boolean;
  tone?: "ok" | "danger";
}

/** Move flow: pick a class -> see valid slots -> drop -> preview the repair -> apply / discard -> undo. */
export function useMoveEditor() {
  const { data, setData } = useTimetable();
  const [moving, setMoving] = useState<Session | null>(null);
  const [options, setOptions] = useState<Map<string, MoveOption> | null>(null);
  const [busy, setBusy] = useState(false);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [changedIds, setChangedIds] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<Toast | null>(null);

  const cancel = useCallback(() => {
    setMoving(null);
    setOptions(null);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !proposal && cancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cancel, proposal]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), toast.undo ? 8000 : 5000);
    return () => clearTimeout(t);
  }, [toast]);

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
    [moving, cancel],
  );

  const drop = useCallback(
    async (day: string, start: string) => {
      if (!moving || !options) return;
      const opt = options.get(`${day}|${start}`);
      if (!opt || opt.status === "blocked") return;
      setBusy(true);
      try {
        setProposal(await api.propose({ session_id: moving.id, day, start_period: opt.start_period }));
      } catch (e) {
        setToast({ text: e instanceof Error ? e.message : "That move isn't possible", tone: "danger" });
      } finally {
        setBusy(false);
      }
    },
    [moving, options],
  );

  const apply = useCallback(async () => {
    if (!proposal) return;
    setBusy(true);
    try {
      const out = await api.apply(proposal.id);
      setData(out);
      setChangedIds(new Set(proposal.changes.map((c) => c.session_id)));
      setToast({ text: proposal.message, undo: true, tone: "ok" });
      setProposal(null);
      cancel();
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : "Couldn't apply the change", tone: "danger" });
      setProposal(null);
    } finally {
      setBusy(false);
    }
  }, [proposal, setData, cancel]);

  const discard = useCallback(() => {
    if (proposal) api.discard(proposal.id);
    setProposal(null);
  }, [proposal]);

  const undo = useCallback(async () => {
    setBusy(true);
    try {
      setData(await api.undo());
      setChangedIds(new Set());
      setToast({ text: "Change undone. The timetable is back to how it was.", tone: "ok" });
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : "Nothing to undo", tone: "danger" });
    } finally {
      setBusy(false);
    }
  }, [setData]);

  const edit: EditState | undefined = data
    ? { movingId: moving?.id ?? null, options, busy, changedIds, onPick: pick, onDrop: drop }
    : undefined;

  return { edit, moving, options, busy, proposal, apply, discard, cancel, undo, toast, setToast };
}
