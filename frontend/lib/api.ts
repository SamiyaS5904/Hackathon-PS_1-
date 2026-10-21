import type { AuditEntry, College, Job, MoveOption, Precheck, Proposal, TimetableOut } from "./types";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
export const ORG = "demo"; // Stage 4: comes from the logged-in user's membership.

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Is the backend running?");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  college: () => request<College>(`/api/orgs/${ORG}/college`),
  precheck: () => request<Precheck>(`/api/orgs/${ORG}/precheck`),
  timetable: () => request<TimetableOut>(`/api/orgs/${ORG}/timetable`),
  generate: (timeLimit = 45) =>
    request<Job>(`/api/orgs/${ORG}/timetable/generate`, {
      method: "POST",
      body: JSON.stringify({ time_limit: timeLimit }),
    }),
  job: (id: string) => request<Job>(`/api/orgs/${ORG}/jobs/${id}`),
  moveOptions: (sessionId: string) =>
    request<MoveOption[]>(`/api/orgs/${ORG}/timetable/sessions/${sessionId}/options`),
  propose: (body: { session_id: string; day: string; start_period: number; venue_id?: string | null }) =>
    request<Proposal>(`/api/orgs/${ORG}/proposals`, { method: "POST", body: JSON.stringify(body) }),
  apply: (id: string) => request<TimetableOut>(`/api/orgs/${ORG}/proposals/${id}/apply`, { method: "POST" }),
  discard: (id: string) =>
    fetch(`${BASE}/api/orgs/${ORG}/proposals/${id}`, { method: "DELETE" }).catch(() => undefined),
  audit: () => request<AuditEntry[]>(`/api/orgs/${ORG}/audit`),
  undo: () => request<TimetableOut>(`/api/orgs/${ORG}/audit/undo`, { method: "POST" }),
};
