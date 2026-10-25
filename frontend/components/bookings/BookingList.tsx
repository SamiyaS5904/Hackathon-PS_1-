"use client";

import clsx from "clsx";
import { AlertTriangle, CalendarClock, Loader2, MapPin, Users, X } from "lucide-react";
import { useState } from "react";
import { Badge, Card } from "@/components/ui";
import { api } from "@/lib/api";
import type { Booking } from "@/lib/types";

/** Upcoming bookings with live clash warnings. ``viewer`` decides whose name is shown on each row. */
export function BookingList({ items, viewer, onChange, empty, onFindAnother }: {
  items: Booking[];
  viewer: "teacher" | "student" | "staff";
  onChange: (items: Booking[]) => void;
  empty: string;
  onFindAnother?: (b: Booking) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cancel = async (b: Booking) => {
    setBusy(b.id);
    setError(null);
    try {
      onChange(await api.cancelBooking(b.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't cancel");
    } finally {
      setBusy(null);
    }
  };

  if (items.length === 0) {
    return (
      <Card className="flex items-center gap-3 p-5 text-sm text-muted">
        <CalendarClock size={18} aria-hidden /> {empty}
      </Card>
    );
  }
  return (
    <div className="space-y-2">
      {error && <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {items.map((b) => {
        const who = b.kind === "doubt"
          ? viewer === "student" ? b.teacher_names.join(", ") : `${b.student_name} (${b.section})`
          : b.teacher_names.join(", ");
        const cancelled = b.status === "cancelled";
        return (
          <Card key={b.id} className={clsx("p-4", cancelled && "opacity-60")}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{b.label} · {b.start}-{b.end}</span>
                  <Badge tone={b.kind === "meeting" ? "accent" : "neutral"}>{b.kind === "meeting" ? "Meeting" : "Doubt slot"}</Badge>
                  {cancelled && <Badge tone="danger">Cancelled{b.cancelled_by ? ` by ${b.cancelled_by}` : ""}</Badge>}
                </div>
                <p className={clsx("mt-1 text-sm", cancelled && "line-through")}>{b.title}</p>
                <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                  <span className="flex items-center gap-1"><Users size={12} aria-hidden /> {who}</span>
                  {b.place && <span className="flex items-center gap-1"><MapPin size={12} aria-hidden /> {b.place}</span>}
                  {b.kind === "meeting" && <span>Booked by {b.created_by_name}</span>}
                </p>
              </div>
              {!cancelled && (
                <button onClick={() => cancel(b)} disabled={busy === b.id}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted hover:bg-surface-2 hover:text-danger">
                  {busy === b.id ? <Loader2 size={13} className="animate-spin" /> : <X size={13} />} Cancel
                </button>
              )}
            </div>
            {b.clash && !cancelled && (
              <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn" role="alert">
                <AlertTriangle size={14} className="shrink-0" aria-hidden />
                <span className="flex-1">The timetable changed: {b.clash}. Pick another time.</span>
                {onFindAnother && (
                  <button onClick={() => onFindAnother(b)} className="font-medium underline">Find another time</button>
                )}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}
