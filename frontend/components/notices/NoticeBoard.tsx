"use client";

import { Megaphone, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card } from "@/components/ui";
import { extraApi } from "@/lib/api";
import { isStaff, useAuth } from "@/lib/auth";
import { useTimetable } from "@/lib/timetable-context";
import type { Notice } from "@/lib/types";
import { NoticeComposer } from "./NoticeComposer";

/** Notices on Home: what the Coordinator / College Admin posted for you, until it expires. Staff can post. */
export function NoticeBoard() {
  const { role } = useAuth();
  const { college } = useTimetable();
  const [items, setItems] = useState<Notice[] | null>(null);
  const [writing, setWriting] = useState(false);
  const staff = isStaff(role);

  const load = useCallback(() => {
    extraApi.notices().then(setItems).catch(() => setItems([]));
  }, []);
  useEffect(load, [load]);

  const remove = async (id: string) => {
    await extraApi.deleteNotice(id).catch(() => undefined);
    load();
  };

  // Nothing to show and nothing to post: stay out of the way.
  if (!items || (items.length === 0 && !staff)) return null;
  return (
    <Card className="mt-6 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-semibold"><Megaphone size={16} className="text-accent-text" aria-hidden /> Notices</h2>
        {staff && college && !writing && (
          <Button onClick={() => setWriting(true)}><Plus size={15} aria-hidden /> New notice</Button>
        )}
      </div>
      {writing && college && (
        <NoticeComposer college={college} onClose={() => setWriting(false)} onPosted={() => { setWriting(false); load(); }} />
      )}
      {items.length === 0 ? (
        !writing && <p className="mt-2 text-sm text-muted">No notices. Post one for your teachers, a year or a section; it also rings their bell.</p>
      ) : (
        <ul className="mt-3 divide-y divide-border">
          {items.map((n) => (
            <li key={n.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{n.title}</p>
                {n.body && <p className="mt-0.5 whitespace-pre-line text-sm text-muted">{n.body}</p>}
                <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                  <span>{n.created_by_name}</span>
                  {staff && <Badge>{n.for_whom}</Badge>}
                  <span>until {n.expires}</span>
                </p>
              </div>
              {n.can_delete && (
                <button onClick={() => remove(n.id)} aria-label="Remove notice" title="Remove notice"
                  className="rounded p-1.5 text-muted hover:bg-surface-2 hover:text-danger"><Trash2 size={14} /></button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
