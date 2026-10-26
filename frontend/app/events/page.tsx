"use client";

import { useCallback, useEffect, useState } from "react";
import { EventList } from "@/components/events/EventList";
import { RoomFinder } from "@/components/events/RoomFinder";
import { ErrorCard, PageHeader, Skeleton } from "@/components/ui";
import { extraApi } from "@/lib/api";
import { isStaff, useAuth } from "@/lib/auth";
import { useTimetable } from "@/lib/timetable-context";
import type { VenueEventLists } from "@/lib/types";

/** Secondary page (root CLAUDE.md §2A): book a free room for an event; Coordinators / Admin approve. */
export default function EventsPage() {
  const { role } = useAuth();
  const { college } = useTimetable();
  const [lists, setLists] = useState<VenueEventLists | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLists(await extraApi.venueEvents());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load room bookings");
    }
  }, []);
  useEffect(() => {
    if (role && role !== "student") load();
  }, [role, load]);

  if (!role) return null;
  if (role === "student") {
    return <ErrorCard message="Rooms for events are booked by teachers and staff. Ask your teacher or club in-charge." />;
  }
  const staff = isStaff(role);
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Room booking"
        subtitle={staff
          ? "Approve requests for your rooms, and book free rooms for events. An approved event holds the room for that date."
          : "Book a free room for a club event, talk or contest. The room's Department Coordinator approves it, and you are told."} />
      {error && <ErrorCard message={error} onRetry={load} />}
      <div className="space-y-6">
        {staff && lists && lists.to_review.length > 0 && (
          <section>
            <h2 className="mb-2 text-sm font-semibold">Waiting for your approval ({lists.to_review.length})</h2>
            <EventList items={lists.to_review} empty="" onChange={load} />
          </section>
        )}
        {college ? <RoomFinder college={college} onBooked={load} /> : <Skeleton className="h-48 w-full" />}
        <section>
          <h2 className="mb-2 text-sm font-semibold">Your bookings</h2>
          {lists ? <EventList items={lists.mine} empty="No room bookings yet. Pick a date and time above." onChange={load} />
            : !error && <Skeleton className="h-20 w-full" />}
        </section>
        {staff && lists && lists.upcoming.length > 0 && (
          <section>
            <h2 className="mb-2 text-sm font-semibold">Coming up in rooms you look after</h2>
            <EventList items={lists.upcoming} empty="" onChange={load} />
          </section>
        )}
      </div>
    </div>
  );
}
