import type {
  AuditEntry, AuthOut, College, Insight, DepartmentReadiness, DeptData, Department, ImportOut, InviteOut, Job, Member,
  MoveOption, OrgInfo, OverrideOut, Precheck, Proposal, Rule, SetupSaved, Settings, SuggestResult, TimeBlock,
  TimetableOut, Venue, WeekOut,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

/** Set by AuthProvider: the login token and the college currently open. */
const session = { token: "", org: "", onUnauthorized: () => {} };

/** Token + college for other services (the assistant). */
export function getSession(): { token: string; org: string } {
  return { token: session.token, org: session.org };
}

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
  // ---- setup ----
  settings: () => request<Settings>(`${org()}/settings`),
  saveSettings: (s: Settings) => request<SetupSaved>(`${org()}/settings`, { method: "PUT", body: JSON.stringify(s) }),
  saveDepartments: (departments: Department[], shared_venues: Venue[]) =>
    request<SetupSaved>(`${org()}/departments`, { method: "PUT", body: JSON.stringify({ departments, shared_venues }) }),
  deptData: (dept: string) => request<DeptData>(`${org()}/departments/${dept}/data`),
  saveDeptData: (dept: string, d: DeptData) =>
    request<SetupSaved>(`${org()}/departments/${dept}/data`, { method: "PUT", body: JSON.stringify(d) }),
  suggest: (dept: string, allotment_ids: string[] = []) =>
    request<SuggestResult>(`${org()}/departments/${dept}/suggest`, post({ allotment_ids })),
  assign: (dept: string, assignments: Record<string, string | null>) =>
    request<SetupSaved>(`${org()}/departments/${dept}/allotments`, { method: "PUT", body: JSON.stringify({ assignments }) }),
  ready: (dept: string, ready: boolean) => request<SetupSaved>(`${org()}/departments/${dept}/ready`, post({ ready })),
  readiness: () => request<DepartmentReadiness[]>(`${org()}/readiness`),
  importExcel: async (dept: string, file: File, commit: boolean) => {
    const form = new FormData();
    form.append("file", file);
    let res: Response;
    try {
      res = await fetch(`${BASE}${org()}/departments/${dept}/import?commit=${commit}`, {
        method: "POST", body: form, headers: { Authorization: `Bearer ${session.token}` },
      });
    } catch {
      throw new ApiError(0, "Can't reach the server. Is the backend running?");
    }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(res.status, typeof body.detail === "string" ? body.detail : "Upload failed");
    return body as ImportOut;
  },
  downloadTemplate: async (dept: string) => {
    const res = await fetch(`${BASE}${org()}/departments/${dept}/template`, {
      headers: { Authorization: `Bearer ${session.token}` },
    });
    if (!res.ok) throw new ApiError(res.status, "Couldn't download the template");
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `timetabl-${session.org}-${dept}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  },
  saveSectionShifts: (shifts: Record<string, string>) =>
    request<SetupSaved>(`${org()}/section-shifts`, { method: "PUT", body: JSON.stringify({ shifts }) }),
  insights: () => request<Insight[]>(`${org()}/insights`),
  rules: () => request<Rule[]>(`${org()}/rules`),
  saveRules: (rules: Rule[]) => request<SetupSaved>(`${org()}/rules`, { method: "PUT", body: JSON.stringify({ rules }) }),
  myBlocked: () => request<{ blocked: TimeBlock[]; message: string }>(`${org()}/me/blocked`),
  saveMyBlocked: (blocked: TimeBlock[]) =>
    request<{ blocked: TimeBlock[]; message: string }>(`${org()}/me/blocked`, { method: "PUT", body: JSON.stringify({ blocked }) }),
};
