"use client";

import { ActivityPanel } from "@/components/changes/ActivityPanel";
import { DayChangesPanel } from "@/components/changes/DayChangesPanel";
import { RequestsPanel } from "@/components/changes/RequestsPanel";
import { PageHeader } from "@/components/ui";
import { isStaff, useAuth } from "@/lib/auth";

const SUBTITLE = {
  staff: "Everything that changes the timetable in one place: teachers' requests waiting for you, classes cancelled or moved for a day, and the latest changes (with Undo).",
  teacher: "Your requests to move lectures for good, and your lectures that are cancelled or moved for a day.",
  student: "Your classes that are cancelled or moved for a day, this week and next.",
};

/** Core page: every kind of change, by role. */
export default function ChangesPage() {
  const { role } = useAuth();
  if (!role) return null;
  const staff = isStaff(role);
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Changes" subtitle={SUBTITLE[staff ? "staff" : role === "teacher" ? "teacher" : "student"]} />
      <div className="space-y-8">
        {(staff || role === "teacher") && <RequestsPanel embedded />}
        <DayChangesPanel />
        {staff && <ActivityPanel embedded limit={8} />}
      </div>
    </div>
  );
}
