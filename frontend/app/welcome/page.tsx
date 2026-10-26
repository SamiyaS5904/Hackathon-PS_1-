import type { Metadata } from "next";
import { Landing } from "@/components/landing/Landing";

export const metadata: Metadata = {
  title: "Timetabl.ai: clash-free college timetables",
  description: "Clash-free college timetables made in minutes and kept right all semester, with an AI assistant that plans the fix.",
};

export default function WelcomePage() {
  return <Landing />;
}
