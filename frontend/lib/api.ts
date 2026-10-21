import type {
  AuditEntry, AuthOut, College, InviteOut, Job, Member, MoveOption, OrgInfo, OverrideOut, Precheck, Proposal,
  TimetableOut, WeekOut,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

/** Set by AuthProvider: the login token and the college currently open. */
const session = { token: "", org: "", onUnauthorized: () => {} };

export function setSession(token: string, org: string, onUnauthorized: () => void) {
  session.token = token;
  session.org = org;
  session.onUnauthorized = onUnauthorized;
}

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
      headers: {
        "Content-Type": "application/json",
        ...(session.token ? { Authorization: `Bearer ${session.token}` } : {}),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Is the backend running?");
  }
  if (res.status === 401 && session.token) session.onUnauthorized();
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`;
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const org = () => `/api/orgs/${session.org}`;
const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const auth = {
  login: (email: string, password: string) => request<AuthOut>("/api/auth/login", post({ email, password })),
  signup: (body: { name: string; email: string; password: string; college_name: string }) =>
    request<AuthOut>("/api/auth/signup", post(body)),
  me: () => request<AuthOut>("/api/me"),
  invite: (token: string) => request<InviteOut>(`/api/invites/${token}`),
  accept: (token: string, name: string, password: string) =>
    request<AuthOut>(`/api/invites/${token}/accept`, post({ name, password })),
};

export const api = {
  org: () => request<OrgInfo>(org()),
  college: () => request<College>(`${org()}/college`),
  loadSample: () => request<College>(`${org()}/load-sample`, { method: "POST" }),
  precheck: () => request<Precheck>(`${org()}/precheck`),
  timetable: () => request<TimetableOut>(`${org()}/timetable`),
  generate: (timeLimit = 45) => request<Job>(`${org()}/timetable/generate`, post({ time_limit: timeLimit })),
  job: (id: string) => request<Job>(`${org()}/jobs/${id}`),
  moveOptions: (sessionId: string) => request<MoveOption[]>(`${org()}/timetable/sessions/${sessionId}/options`),
  propose: (body: { session_id: string; day: string; start_period: number; venue_id?: string | null }) =>
    request<Proposal>(`${org()}/proposals`, post(body)),
  apply: (id: string) => request<TimetableOut>(`${org()}/proposals/${id}/apply`, { method: "POST" }),
  discard: (id: string) => request<void>(`${org()}/proposals/${id}`, { method: "DELETE" }).catch(() => undefined),
  audit: () => request<AuditEntry[]>(`${org()}/audit`),
  undo: () => request<TimetableOut>(`${org()}/audit/undo`, { method: "POST" }),
  week: (start: string) => request<WeekOut>(`${org()}/timetable/week?start=${start}`),
  dayOptions: (sessionId: string, date: string, toDate: string) =>
    request<MoveOption[]>(`${org()}/timetable/sessions/${sessionId}/day-options?date=${date}&to_date=${toDate}`),
  addOverride: (body: {
    session_id: string; date: string; kind: "cancel" | "move"; to_date?: string; start_period?: number; reason?: string;
  }) => request<OverrideOut>(`${org()}/overrides`, post(body)),
  removeOverride: (id: string) => request<OverrideOut>(`${org()}/overrides/${id}`, { method: "DELETE" }),
  members: () => request<Member[]>(`${org()}/members`),
  invites: () => request<InviteOut[]>(`${org()}/invites`),
  invite: (body: { email: string; role: string; department_id?: string | null; teacher_id?: string | null }) =>
    request<InviteOut>(`${org()}/invites`, post(body)),
};
