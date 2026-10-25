"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { useAuth } from "./auth";
import type { College, Job, Precheck, TimetableOut } from "./types";

export const GENERATE_SECONDS = 45;

interface State {
  college: College | null;
  data: TimetableOut | null;
  precheck: Precheck | null;
  loading: boolean;
  error: string | null;
  job: Job | null;
  generate: () => Promise<void>;
  reload: () => Promise<void>;
  setData: (d: TimetableOut) => void;
}

const Ctx = createContext<State | null>(null);

export function TimetableProvider({ children }: { children: React.ReactNode }) {
  const [college, setCollege] = useState<College | null>(null);
  const [data, setData] = useState<TimetableOut | null>(null);
  const [precheck, setPrecheck] = useState<Precheck | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const { member } = useAuth();
  const orgId = member?.org_id;
  const staff = member?.role === "admin" || member?.role === "coordinator";

  const loadTimetable = useCallback(async () => {
    try {
      setData(await api.timetable());
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setData(null);
      else throw e;
    }
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // All at once; the data checks only matter to staff (their dashboard and Generate button).
      const [c, p] = await Promise.all([
        api.college(),
        staff ? api.precheck() : Promise.resolve(null),
        loadTimetable(),
      ]);
      setCollege(c);
      setPrecheck(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }, [loadTimetable, staff]);

  useEffect(() => {
    if (!orgId) return;
    setData(null);
    reload();
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [reload, orgId]);

  const generate = useCallback(async () => {
    setError(null);
    try {
      const started = await api.generate(GENERATE_SECONDS);
      setJob(started);
      timer.current = setInterval(async () => {
        try {
          const j = await api.job(started.id);
          setJob(j);
          if (j.status !== "running") {
            if (timer.current) clearInterval(timer.current);
            if (j.status === "failed") setError(j.error ?? "Generation failed");
            await loadTimetable();
          }
        } catch (e) {
          if (timer.current) clearInterval(timer.current);
          setError(e instanceof Error ? e.message : "Lost contact with the server");
          setJob(null);
        }
      }, 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start generation");
    }
  }, [loadTimetable]);

  return (
    <Ctx.Provider value={{ college, data, precheck, loading, error, job, generate, reload, setData }}>
      {children}
    </Ctx.Provider>
  );
}

export function useTimetable(): State {
  const v = useContext(Ctx);
  if (!v) throw new Error("useTimetable must be used inside TimetableProvider");
  return v;
}

/** The timetable context, or null outside a college (the platform owner's pages). */
export function useTimetableOptional(): State | null {
  return useContext(Ctx);
}

export const isGenerating = (job: Job | null) => job?.status === "running";
