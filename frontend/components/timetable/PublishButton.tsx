"use client";

import { Loader2, Send } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useTimetable } from "@/lib/timetable-context";

/** Admin's core action after reviewing a draft: teachers and students see the timetable from now on. */
export function PublishButton() {
  const { data, setData } = useTimetable();
  const [step, setStep] = useState<"idle" | "confirm" | "busy">("idle");
  const [error, setError] = useState<string | null>(null);
  if (!data || data.stale || data.timetable.published_at || data.timetable.sessions.length === 0) return null;

  const publish = async () => {
    setStep("busy");
    setError(null);
    try {
      setData(await api.publish());
      setStep("idle");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't publish. Please try again.");
      setStep("confirm");
    }
  };

  if (step === "idle") {
    return (
      <Button variant="primary" onClick={() => setStep("confirm")}>
        <Send size={16} aria-hidden /> Publish
      </Button>
    );
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-2" role="group" aria-label="Confirm publishing">
      <span className="text-xs text-muted">{error ?? "Teachers and students will see it and get a notification."}</span>
      <Button onClick={() => setStep("idle")} disabled={step === "busy"}>Cancel</Button>
      <Button variant="primary" onClick={publish} disabled={step === "busy"} autoFocus>
        {step === "busy" ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Send size={16} aria-hidden />}
        Publish to everyone
      </Button>
    </span>
  );
}
