import type {
  AuditEntry, AuthOut, Booking, BookingSlot, BookResult, ChangeRequest, CollegeSummary, SetupStatus, TodayReport, OfficeHour, PlatformOverview, SectioningOptions, SectioningOut, TeacherHours, ClassAttendance, Feed, MakeupOption, SectionAttendance, StudentAttendance, TeacherClass, College, Insight, DepartmentReadiness, DeptData, Department, ImportOut, InviteOut, Job, Member,
  MoveOption, OrgInfo, OverrideOut, Precheck, Proposal, Rule, SetupSaved, Settings, SuggestResult, TimeBlock,
  TimetableOut, Venue, WeekOut, RescheduleOut, FreeVenue, VenueEventLists, VenueEventResult,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const NETWORK = "Can't reach Timetabl.ai right now. Check the internet connection and try again.";

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
    throw new ApiError(0, NETWORK);
  }
  if (res.status === 401 && session.token) session.onUnauthorized();
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail
      : res.status >= 500 ? "Something went wrong on our side. Please try again in a moment." : "That didn't work. Please try again.";
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
  makeup: (sessionId: string, date: string) =>
    request<MakeupOption[]>(`${org()}/timetable/sessions/${sessionId}/makeup?date=${date}&days=7`),
  classAttendance: (sessionId: string, date: string) =>
    request<ClassAttendance>(`${org()}/attendance/class?session_id=${sessionId}&date=${date}`),
  saveAttendance: (sessionId: string, date: string, absent: string[]) =>
    request<ClassAttendance>(`${org()}/attendance/class`, { method: "PUT", body: JSON.stringify({ session_id: sessionId, date, absent }) }),
  myClasses: () => request<TeacherClass[]>(`${org()}/attendance/my-classes`),
  myAttendance: () => request<StudentAttendance>(`${org()}/attendance/me`),
  sectionAttendance: (sectionId: string) => request<SectionAttendance>(`${org()}/attendance/sections/${sectionId}`),
  setAttendanceRule: (minPercent: number) =>
    request<{ min_percent: number; message: string }>(`${org()}/attendance/rule`, { method: "PUT", body: JSON.stringify({ min_percent: minPercent }) }),
  changeRequests: () => request<ChangeRequest[]>(`${org()}/change-requests`),
  requestChange: (body: { session_id: string; day: string; start_period: number; reason: string }) =>
    request<ChangeRequest>(`${org()}/change-requests`, post(body)),
  reviewRequest: (id: string) => request<Proposal>(`${org()}/change-requests/${id}/review`, { method: "POST" }),
  declineRequest: (id: string, note: string) =>
    request<ChangeRequest>(`${org()}/change-requests/${id}/decline`, post({ note })),
  withdrawRequest: (id: string) =>
    request<ChangeRequest>(`${org()}/change-requests/${id}/withdraw`, { method: "POST" }),
  notifications: () => request<Feed>(`${org()}/notifications`),
  // Platform owner (Super Admin): not tied to one college
  platformOverview: () => request<PlatformOverview>("/api/platform/overview"),
  updateCollege: (id: string, body: { plan?: string; status?: string; note?: string }) =>
    request<CollegeSummary>(`/api/platform/colleges/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  // Teacher booking
  myBookings: (includePast = false) => request<Booking[]>(`${org()}/bookings?include_past=${includePast}`),
  cancelBooking: (id: string) => request<Booking[]>(`${org()}/bookings/${id}/cancel`, { method: "POST" }),
  officeHours: () => request<OfficeHour[]>(`${org()}/bookings/office-hours`),
  addOfficeHour: (body: { day: string; start: string; end: string; seats: number; place: string }) =>
    request<OfficeHour[]>(`${org()}/bookings/office-hours`, post(body)),
  removeOfficeHour: (id: string) => request<OfficeHour[]>(`${org()}/bookings/office-hours/${id}`, { method: "DELETE" }),
  bookingTeachers: () => request<TeacherHours[]>(`${org()}/bookings/teachers`),
  doubtSlots: (teacherId?: string) =>
    request<BookingSlot[]>(`${org()}/bookings/doubt-slots${teacherId ? `?teacher_id=${teacherId}` : ""}`),
  bookDoubt: (body: { office_hour_id: string; date: string; topic: string }) =>
    request<BookResult>(`${org()}/bookings/doubt`, post(body)),
  meetingTimes: (body: { teacher_ids: string[]; days: number; periods: number }) =>
    request<BookingSlot[]>(`${org()}/bookings/meeting-times`, post(body)),
  bookMeeting: (body: { teacher_ids: string[]; date: string; start: string; end: string; title: string; place: string }) =>
    request<BookResult>(`${org()}/bookings/meetings`, post(body)),
  seenNotifications: () => request<void>(`${org()}/notifications/seen`, { method: "POST" }),
  publish: () => request<TimetableOut>(`${org()}/timetable/publish`, { method: "POST" }),
  generate: (timeLimit = 45, keepCurrent = false) =>
    request<Job>(`${org()}/timetable/generate`, post({ time_limit: timeLimit, keep_current: keepCurrent })),
  job: (id: string) => request<Job>(`${org()}/jobs/${id}`),
  moveOptions: (sessionId: string) => request<MoveOption[]>(`${org()}/timetable/sessions/${sessionId}/options`),
  propose: (body: { session_id: string; day: string; start_period: number; venue_id?: string | null }) =>
    request<Proposal>(`${org()}/proposals`, post(body)),
  apply: (id: string) => request<TimetableOut>(`${org()}/proposals/${id}/apply`, { method: "POST" }),
  discard: (id: string) => request<void>(`${org()}/proposals/${id}`, { method: "DELETE" }).catch(() => undefined),
  audit: () => request<AuditEntry[]>(`${org()}/audit`),
  /** Undo the latest change; with ``entryId``, only if that exact change is still the latest. */
  undo: (entryId?: string) => request<TimetableOut>(`${org()}/audit/undo`, post(entryId ? { entry_id: entryId } : {})),
  week: (start: string) => request<WeekOut>(`${org()}/timetable/week?start=${start}`),
  dayOptions: (sessionId: string, date: string, toDate: string) =>
    request<MoveOption[]>(`${org()}/timetable/sessions/${sessionId}/day-options?date=${date}&to_date=${toDate}`),
  addOverride: (body: {
    session_id: string; date: string; kind: "cancel" | "move"; to_date?: string; start_period?: number; reason?: string; via?: "app" | "chatbot";
  }) => request<OverrideOut>(`${org()}/overrides`, post(body)),
  removeOverride: (id: string) => request<OverrideOut>(`${org()}/overrides/${id}`, { method: "DELETE" }),
  /** Several one-day changes as one step: all or nothing, one log entry, one notification. */
  batchOverrides: (body: { title: string; changes: { session_id: string; date: string; kind: "cancel" | "move"; reason?: string }[] }) =>
    request<OverrideOut>(`${org()}/overrides/batch`, post(body)),
  today: (date?: string) => request<TodayReport>(`${org()}/today${date ? `?date=${date}` : ""}`),
  setupStatus: () => request<SetupStatus>(`${org()}/setup-status`),
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
      throw new ApiError(0, NETWORK);
    }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(res.status, typeof body.detail === "string" ? body.detail : "Upload failed");
    return body as ImportOut;
  },
  autoSections: async (dept: string, file: File, o: SectioningOptions, commit: boolean) => {
    const form = new FormData();
    form.append("file", file);
    const q = new URLSearchParams({ year: String(o.year), max_size: String(o.max_size), batches: String(o.batches),
      commit: String(commit), ...(o.shift_id ? { shift_id: o.shift_id } : {}), ...(o.mix_by ? { mix_by: o.mix_by } : {}),
      ...(o.prefix ? { prefix: o.prefix } : {}) });
    let res: Response;
    try {
      res = await fetch(`${BASE}${org()}/departments/${dept}/auto-sections?${q}`, {
        method: "POST", body: form, headers: { Authorization: `Bearer ${session.token}` },
      });
    } catch {
      throw new ApiError(0, NETWORK);
    }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(res.status, typeof body.detail === "string" ? body.detail : "Upload failed");
    return body as SectioningOut;
  },
  downloadYearTemplate: async (dept: string) => {
    const res = await fetch(`${BASE}${org()}/departments/${dept}/year-list-template`, {
      headers: { Authorization: `Bearer ${session.token}` },
    });
    if (!res.ok) throw new ApiError(res.status, "Couldn't download the template");
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `year-list-${dept}.xlsx`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
  /** The uploaded sheet back with every problem row highlighted and explained. */
  downloadMarked: async (dept: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}${org()}/departments/${dept}/import/marked`, {
      method: "POST", body: form, headers: { Authorization: `Bearer ${session.token}` },
    }).catch(() => { throw new ApiError(0, NETWORK); });
    if (!res.ok) throw new ApiError(res.status, "Couldn't prepare the marked sheet");
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `${dept}-with-problems-marked.xlsx`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
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
  /** Excel or PDF of one section / teacher / room, or all of them (no id; staff only). */
  exportTimetable: async (format: "xlsx" | "pdf", view: string, id?: string) => {
    const q = new URLSearchParams({ format, view, ...(id ? { id } : {}) });
    let res: Response;
    try {
      res = await fetch(`${BASE}${org()}/export?${q}`, { headers: { Authorization: `Bearer ${session.token}` } });
    } catch {
      throw new ApiError(0, NETWORK);
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, typeof body.detail === "string" ? body.detail : "Couldn't download the file");
    }
    const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? `timetable.${format}`;
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
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

/** Reschedule finder, room booking for events and notices (own object so it merges cleanly with `api`). */
export const extraApi = {
  reschedule: (sessionId: string, date: string) =>
    request<RescheduleOut>(`${org()}/timetable/sessions/${sessionId}/reschedule?date=${date}&days=7`),
  freeVenues: (date: string, start: string, end: string, minSeats = 0) =>
    request<FreeVenue[]>(`${org()}/venue-events/free?${new URLSearchParams({ date, start, end, min_seats: String(minSeats) })}`),
  bookVenue: (body: { venue_id: string; date: string; start: string; end: string; title: string; club: string }) =>
    request<VenueEventResult>(`${org()}/venue-events`, post(body)),
  venueEvents: () => request<VenueEventLists>(`${org()}/venue-events`),
  approveVenueEvent: (id: string) => request<VenueEventResult>(`${org()}/venue-events/${id}/approve`, { method: "POST" }),
  declineVenueEvent: (id: string, note: string) => request<VenueEventResult>(`${org()}/venue-events/${id}/decline`, post({ note })),
  cancelVenueEvent: (id: string) => request<VenueEventResult>(`${org()}/venue-events/${id}/cancel`, { method: "POST" }),
};
