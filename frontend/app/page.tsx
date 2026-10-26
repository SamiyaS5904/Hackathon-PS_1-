"use client";

import { PersonalHome } from "@/components/home/PersonalHome";
import { StaffHome } from "@/components/home/StaffHome";
import { isStaff, useAuth } from "@/lib/auth";

/** Home, by role: staff get setup progress, the next step and Today; teachers and students get their day and week. */
export default function Home() {
  const { role } = useAuth();
  if (!role) return null;
  return isStaff(role) ? <StaffHome /> : <PersonalHome />;
}
