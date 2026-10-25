"use client";

import { useCallback, useEffect, useState } from "react";
import { BookingList } from "@/components/bookings/BookingList";
import { DoubtBooker } from "@/components/bookings/DoubtBooker";
import { MeetingPlanner } from "@/components/bookings/MeetingPlanner";
import { OfficeHoursEditor } from "@/components/bookings/OfficeHoursEditor";
import { ErrorCard, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { isStaff, useAuth } from "@/lib/auth";
import type { Booking, OfficeHour } from "@/lib/types";

const SUBTITLE = {
  teacher: "Set weekly office hours: students book doubt slots in them. Meetings your Coordinator books show here too. Nothing ever clashes with your classes.",
  student: "Book a doubt slot with a teacher at a time when you have no class.",
  staff: "Find a time when the teachers you need are all free, and book a meeting with one click.",
};

/** Secondary page (root CLAUDE.md §2A): teacher booking. Bookings sit beside the timetable and never move a class. */
export default function BookingsPage() {
  const { role } = useAuth();
  const viewer = role === "teacher" ? "teacher" : role === "student" ? "student" : "staff";
  const [items, setItems] = useState<Booking[] | null>(null);
  const [hours, setHours] = useState<OfficeHour[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryTeacher, setRetryTeacher] = useState<string | undefined>();
  const [retryTeachers, setRetryTeachers] = useState<string[] | undefined>();

  const load = useCallback(async () => {
    try {
      setItems(await api.myBookings());
      if (role === "teacher") setHours(await api.officeHours());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load bookings");
    }
  }, [role]);
  useEffect(() => {
    if (role) load();
  }, [role, load]);

  // A booking hit by a timetable change: open the booker for the same teacher(s) at the top of the page.
  const findAnother = (b: Booking) => {
    if (b.kind === "doubt") setRetryTeacher(b.teacher_ids[0]);
    else setRetryTeachers([...b.teacher_ids]);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (!role) return null;
  const listTitle = viewer === "staff" ? "Meetings you booked" : viewer === "teacher" ? "Upcoming bookings with you" : "My bookings";
  const empty = viewer === "staff" ? "No meetings booked yet." : viewer === "teacher"
    ? "No bookings yet. Students see your office hours as soon as you add them." : "No bookings yet.";

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Bookings" subtitle={SUBTITLE[viewer]} />
      {error && <ErrorCard message={error} onRetry={load} />}
      <div className="space-y-6">
        {viewer === "teacher" && (hours ? <OfficeHoursEditor hours={hours} onChange={setHours} /> : !error && <Skeleton className="h-40 w-full" />)}
        {viewer === "student" && <DoubtBooker onBooked={load} teacherId={retryTeacher} />}
        {isStaff(role) && <MeetingPlanner onBooked={load} preset={retryTeachers} />}
        <section>
          <h2 className="mb-2 text-sm font-semibold">{listTitle}</h2>
          {items ? (
            <BookingList items={items} viewer={viewer} onChange={setItems} empty={empty}
              onFindAnother={viewer === "teacher" ? undefined : findAnother} />
          ) : !error && <Skeleton className="h-24 w-full" />}
        </section>
      </div>
    </div>
  );
}
