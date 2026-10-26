// Mirrors backend Pydantic models (app/models/domain.py, app/main.py).
// TODO(stage 4): generate from the backend OpenAPI schema instead of hand-writing.

export type Kind = "lecture" | "lab";

export interface Period { start: string; end: string }
export interface LunchRule { window_start: string; window_end: string }
export interface Shift { id: string; name: string; periods: Period[]; lunch: LunchRule | null }
export interface Department { id: string; name: string; short: string }
export interface Venue {
  id: string; name: string; type: "lecture" | "lab" | "seminar"; capacity: number;
  tags: string[]; department_id: string | null;
}
export interface Batch { id: string; name: string; strength: number }
export interface Section {
  id: string; name: string; department_id: string; year: number; strength: number;
  shift_id: string; batches: Batch[];
}
export interface Teacher { id: string; name: string; department_id: string; shift_ids: string[]; max_per_day: number; blocked?: TimeBlock[] }
export interface Subject {
  id: string; code: string; name: string; department_id: string; year: number;
  lectures_per_week: number; labs_per_week: number; lab_tag: string | null;
}
export interface College {
  id: string; name: string; days: string[]; lab_periods: number; shifts: Shift[];
  departments: Department[]; venues: Venue[]; sections: Section[]; teachers: Teacher[]; subjects: Subject[];
  students: Student[];
  teacher_subjects: TeacherSubject[];
  elective_slots: ElectiveSlot[];
  holidays: Holiday[];
  rules: Rule[];
  department_status: Record<string, { ready: boolean; at: number | null; by: string }>;
  attendance_min_percent: number;
  setup_saved?: boolean | null;
  revision: number;
}
export interface ElectiveGroup { id: string; name: string; subject_id: string; teacher_id: string; student_ids: string[] }
export interface ElectiveSlot { id: string; name: string; section_ids: string[]; lectures_per_week: number; groups: ElectiveGroup[] }
export interface Student { id: string; roll_no: string; name: string; email: string; section_id: string; batch_id: string | null }

export interface Session {
  id: string; allotment_id: string; subject_id: string; teacher_id: string; venue_id: string;
  kind: Kind; section_ids: string[]; batch_id: string | null; day: string; shift_id: string;
  start_period: number; length: number; start: string; end: string;
  elective_slot_id: string | null; group_id: string | null;
}
/** One section's lunch on one weekday (chosen per section and per day inside the mess window). */
export interface Lunch {
  shift_id: string; period: number; start: string; end: string;
  section_id: string | null; day: string | null; year?: number | null;
}
export interface Override {
  id: string; session_id: string; date: string; kind: "cancel" | "move"; to_date: string | null;
  start_period: number | null; venue_id: string | null; reason: string; created_by: string;
}
export interface Timetable {
  college_id: string; status: string; sessions: Session[]; lunches: Lunch[]; overrides: Override[];
  messages: string[]; warnings: string[]; solve_seconds: number;
  published_at: number | null; published_by: string;
}
export interface QualityItem { key: string; label: string; value: number; penalty: number; detail: string }
export interface QualityReport {
  score: number; items: QualityItem[];
  teacher_load: Record<string, Record<string, number>>;
  venue_utilisation: Record<string, number>;
}
export interface Violation { type: string; message: string; session_ids: string[] }
export interface LastChange { id: string; at: number; actor: string; action: string; can_undo: boolean }
export interface TimetableOut {
  timetable: Timetable; quality: QualityReport | null; violations: Violation[]; stale: boolean;
  ever_published: boolean;
  last_change?: LastChange | null; // staff only
}
export interface Job { id: string; status: "running" | "done" | "failed"; elapsed: number; error: string | null; message?: string }
export interface Precheck { problems: string[]; warnings: string[]; located?: LocatedProblem[] }

export type ViewKind = "section" | "teacher" | "venue";

export interface MoveOption {
  day: string; start_period: number; start: string; end: string;
  status: "free" | "repair" | "blocked"; reason: string; venue_id: string | null; conflicts: string[];
}
export interface Change { session_id: string; subject: string; sections: string; before: string; after: string }
export interface Proposal {
  id: string; message: string; changes: Change[]; quality_before: number | null; quality_after: number | null;
}
export interface AuditEntry {
  id: string; at: number; action: string; source: string; actor: string; changes: Change[];
  undone: boolean; can_undo: boolean;
}
export type OccurrenceStatus = "normal" | "cancelled" | "moved_out" | "moved_in";
export interface Occurrence {
  session: Session; date: string; status: OccurrenceStatus; override_id: string | null; note: string;
  occurrence_id: string; // "<session id>@<original date>": stable, for future attendance
  substitute_for?: string | null; // the usual teacher's id when a substitute takes this class
}
export interface DayInfo { date: string; day: string; label: string; working: boolean; holiday: string | null }
export interface WeekOut { days: DayInfo[]; occurrences: Occurrence[] }
export interface OverrideOut { message: string; timetable: TimetableOut }

/** Teacher leave and its cover plan (backend app/leave.py). */
export type LeaveStatus = "pending" | "approved" | "declined" | "withdrawn";
export interface Leave {
  id: string; at: number; teacher_id: string; teacher_name: string; department_id: string;
  start_date: string; end_date: string; reason: string; status: LeaveStatus; requested_by: string;
  decided_by: string; decided_at: number | null; note: string; applied_at: number | null; plan_summary: string;
}
export interface CoverOption { teacher_id: string; name: string; score: number; why: string }
export type CoverAction = "substitute" | "cancel";
export interface PlanItem {
  session_id: string; date: string; day_label: string; start: string; end: string; subject: string; sections: string;
  year: number | null; venue: string; action: CoverAction; teacher_id: string | null; teacher_name: string;
  options: CoverOption[]; note: string;
}
export interface LeavePlan {
  teacher_id: string; teacher_name: string; start_date: string; end_date: string; dates: string[]; years: number[];
  items: PlanItem[]; covered: number; cancelled: number; summary: string; problems: string[];
}
export interface CoverChoice { session_id: string; date: string; action: CoverAction; teacher_id: string | null }
export interface LeaveApplied { message: string; leave: Leave; entry_id: string | null }

export interface MakeupOption { date: string; label: string; start_period: number; start: string; end: string; venue_id: string | null; venue: string }
export interface RosterStudent { student_id: string; roll_no: string; name: string }
export interface ClassAttendance {
  occurrence_id: string; session_id: string; date: string; subject: string; sections: string; start: string; end: string;
  venue: string; roster: RosterStudent[]; absent: string[]; marked: boolean; marked_by: string; marked_at: number | null;
  can_edit: boolean; note: string;
}
export interface TeacherClass {
  session_id: string; date: string; label: string; subject: string; sections: string; start: string; end: string;
  venue: string; students: number; marked: boolean; absent: number; can_edit: boolean;
}
export interface SubjectAttendance {
  subject_id: string; code: string; name: string; held: number; attended: number; percent: number | null;
  status: "ok" | "low" | "none"; advice: string;
}
export interface StudentAttendance {
  min_percent: number; held: number; attended: number; percent: number | null; status: "ok" | "low" | "none";
  advice: string; subjects: SubjectAttendance[]; recent: { date: string; subject: string; present: boolean }[];
}
export interface SectionAttendance {
  section: string; min_percent: number;
  students: { student_id: string; roll_no: string; name: string; held: number; attended: number; percent: number | null; low: boolean }[];
}
export interface ChangeRequest {
  id: string; at: number; teacher_name: string; teacher_id: string; session_id: string; day: string;
  start_period: number; summary: string; reason: string; status: "pending" | "approved" | "declined" | "withdrawn";
  decided_by: string; decided_at: number | null; note: string;
}
export interface Notification { id: string; at: number; title: string; body: string; link: string; unread: boolean }
export interface Feed { items: Notification[]; unread: number }

export type Role = "admin" | "coordinator" | "teacher" | "student";
export interface Member {
  user_id: string; org_id: string; org_name: string; name: string; email: string; role: Role;
  department_id: string | null; teacher_id: string | null; section_id: string | null; batch_id: string | null;
}
export interface AuthOut { token: string; user_id: string; name: string; email: string; memberships: Member[]; platform_owner?: boolean }
export interface InviteOut {
  token: string; org_id: string; org_name: string; email: string; role: Role;
  department_id: string | null; teacher_id: string | null; status: string;
}
export interface OrgInfo { id: string; name: string; is_demo: boolean; role: Role; student_accounts: number }

// ---- Stage 5: setup ----
export interface TimeBlock { day: string; start: string; end: string }
export interface Holiday { date: string; label: string }
export interface ShiftFull {
  id: string; name: string; periods: Period[];
  year_breaks: { years: number[]; start: string; end: string; label: string }[];
  lunch: LunchRule | null;
}
export interface Settings {
  days: string[]; lab_periods: number; shifts: ShiftFull[]; holidays: Holiday[];
  semester_start: string | null; semester_end: string | null;
}
export interface TeacherFull extends Teacher { blocked: TimeBlock[] }
export interface Allotment {
  id: string; subject_id: string; teacher_id: string | null; kind: Kind; section_ids: string[]; batch_id: string | null;
}
export interface TeacherSubject { teacher_id: string; subject_id: string; preference: number }
export interface DeptData {
  sections: Section[]; teachers: TeacherFull[]; subjects: Subject[]; venues: Venue[];
  allotments: Allotment[]; teacher_subjects: TeacherSubject[]; students: Student[];
}
export interface SetupSaved { college: College; problems: string[]; warnings: string[] }
export interface Suggestion { allotment_id: string; teacher_id: string | null; reason: string }
export interface SuggestResult { suggestions: Suggestion[]; unfilled: string[]; loads: Record<string, number> }
export interface DepartmentReadiness {
  department_id: string; name: string; ready: boolean; by: string; at: number | null;
  sections: number; teachers: number; subjects: number; classes: number; without_teacher: number; students: number;
}
export interface RowError { sheet: string; row: number; message: string }
export interface ImportOut {
  errors: RowError[]; counts: Record<string, number>; problems: string[]; warnings: string[]; saved: boolean;
}
export interface Rule {
  id: string; name: string; kind: "no_classes" | "max_per_day"; mode: "must" | "try"; weight: number;
  enabled: boolean; department_id: string | null; years: number[]; days: string[];
  after: string | null; before: string | null; max_periods: number | null;
}

// ---- Stage 6: assistant ----
export interface Insight { kind: string; severity: "info" | "warn"; title: string; detail: string; ask: string }
export interface OneDayAction {
  session_id: string; date: string; kind: "cancel" | "move"; to_date?: string; start_period?: number;
  reason: string; summary: string;
}
export interface BookingAction {
  kind: "doubt" | "meeting"; date: string; summary: string;
  office_hour_id?: string; topic?: string; // doubt slot
  teacher_ids?: string[]; start?: string; end?: string; title?: string; place?: string; // meeting
}
export type ChatCard =
  | { type: "proposal"; proposal: Proposal }
  | { type: "one_day"; action: OneDayAction }
  | { type: "booking"; booking: BookingAction }
  | { type: "platform"; change: { org: string; name: string; plan: string | null; status: string | null; note: string | null; summary: string } };
export type ChatEvent =
  | { type: "start"; conversation_id: string }
  | { type: "token"; text: string }
  | { type: "tool"; name: string; label: string; status: "start" | "done" | "error" }
  | { type: "card"; card: ChatCard }
  | { type: "error"; message: string }
  | { type: "done" };

// ---- Teacher booking (office hours, doubt slots, meetings) ----

export interface OfficeHour {
  id: string;
  teacher_id: string;
  day: string;
  start: string;
  end: string;
  seats: number;
  place: string;
}

export interface TeacherHours {
  teacher_id: string;
  name: string;
  department: string;
  teaches_you: boolean;
  hours: OfficeHour[];
}

export interface BookingSlot {
  date: string;
  label: string;
  start: string;
  end: string;
  teacher_id: string | null;
  teacher_name: string;
  office_hour_id: string | null;
  place: string;
  seats_left: number | null;
}

export interface Booking {
  id: string;
  kind: "doubt" | "meeting";
  date: string;
  label: string;
  start: string;
  end: string;
  teacher_ids: string[];
  teacher_names: string[];
  title: string;
  place: string;
  student_name: string;
  section: string;
  created_by: string;
  created_by_name: string;
  status: "booked" | "cancelled";
  cancelled_by: string;
  clash: string | null;
  past: boolean;
}

export interface BookResult {
  message: string;
  booking: Booking;
}

// ---- Auto-sectioning (whole-year list -> sections + lab batches) ----

export interface PlannedSection {
  name: string;
  size: number;
  batches: number[];
  first_roll: string;
  last_roll: string;
  mix: Record<string, number>;
}

export interface SectioningOut {
  errors: { sheet: string; row: number; message: string }[];
  columns: string[];
  plan: { year: number; shift_id: string; students: number; sections: PlannedSection[]; warnings: string[]; replaces: string[] } | null;
  problems: string[];
  saved: boolean;
}

export interface SectioningOptions {
  year: number;
  max_size: number;
  batches: number;
  shift_id?: string;
  mix_by?: string;
  prefix?: string;
}

// ---- Platform owner (Super Admin) ----

export interface CollegeSummary {
  id: string;
  name: string;
  is_demo: boolean;
  created_at: number;
  plan: "trial" | "pro" | "campus";
  status: "active" | "read_only" | "paused";
  note: string;
  stage: string;
  departments: number;
  departments_ready: number;
  sections: number;
  teachers: number;
  students: number;
  accounts: number;
  classes: number;
  published_at: number | null;
  attendance_marked: number;
  bookings: number;
  last_activity: number;
  flags: string[];
  needs_attention: boolean;
}

export interface PlatformOverview {
  colleges: number;
  live: number;
  needs_attention: number;
  students: number;
  teachers: number;
  sections: number;
  classes: number;
  accounts: number;
  attendance_marked: number;
  bookings: number;
  plans: Record<string, number>;
  items: CollegeSummary[];
}

// ---- Staff home (Today) and setup checklist ----

export interface ClassLine {
  session_id: string; occurrence_id: string; subject: string; sections: string; teacher_id: string; teacher: string;
  start: string; end: string; room: string; note: string;
}
export interface TodayReport {
  date: string; label: string; working: boolean; holiday: string | null; classes_today: number;
  away: { teacher_id: string; name: string; classes: number }[];
  cancelled: ClassLine[]; moved: ClassLine[];
  recent: { id: string; at: number; actor: string; action: string; source: string; undone: boolean }[];
  status: { state: "none" | "draft" | "published" | "out_of_date"; published_at: number | null; published_by: string };
  pending_requests: number;
}
export interface SetupStep { key: string; title: string; done: boolean; missing: string; link: string }
export interface SetupStatus { done: boolean; steps: SetupStep[] }
export interface LocatedProblem { message: string; link: string; where: string }
