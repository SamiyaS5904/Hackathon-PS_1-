"use client";

import { PersonalHome } from "@/components/home/PersonalHome";
import { StaffHome } from "@/components/home/StaffHome";
import { NoticeBoard } from "@/components/notices/NoticeBoard";
import { isStaff, useAuth } from "@/lib/auth";

/** Home, by role: staff get setup progress, the next step and Today; teachers and students get their day and week.
 * Notices from the Coordinator / College Admin sit below (staff post them there). */
export default function Home() {
  const { role } = useAuth();
  if (!role) return null;
  const staff = isStaff(role);
  return (
    <>
      {staff ? <StaffHome /> : <PersonalHome />}
      <div className={staff ? "mx-auto max-w-5xl" : "mx-auto max-w-3xl"}><NoticeBoard /></div>
    </>
  );
}
