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
export interface Teacher { id: string; name: string; department_id: string; shift_ids: string[]; max_per_day: number }
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
export interface Lunch { shift_id: string; year: number; period: number; start: string; end: string }
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
export interface TimetableOut {
  timetable: Timetable; quality: QualityReport | null; violations: Violation[]; stale: boolean;
  ever_published: boolean;
}
export interface Job { id: string; status: "running" | "done" | "failed"; elapsed: number; error: string | null }
export interface Precheck { problems: string[]; warnings: string[] }

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
export interface Occurrence { session: Session; date: string; status: OccurrenceStatus; override_id: string | null; note: string }
export interface DayInfo { date: string; day: string; label: string; working: boolean; holiday: string | null }
export interface WeekOut { days: DayInfo[]; occurrences: Occurrence[] }
export interface OverrideOut { message: string; timetable: TimetableOut }

export interface Notification { id: string; at: number; title: string; body: string; link: string; unread: boolean }
export interface Feed { items: Notification[]; unread: number }

export type Role = "admin" | "coordinator" | "teacher" | "student";
export interface Member {
  user_id: string; org_id: string; org_name: string; name: string; email: string; role: Role;
  department_id: string | null; teacher_id: string | null; section_id: string | null; batch_id: string | null;
}
export interface AuthOut { token: string; user_id: string; name: string; email: string; memberships: Member[] }
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
export type ChatCard = { type: "proposal"; proposal: Proposal } | { type: "one_day"; action: OneDayAction };
export type ChatEvent =
  | { type: "start"; conversation_id: string }
  | { type: "token"; text: string }
  | { type: "tool"; name: string; label: string; status: "start" | "done" | "error" }
  | { type: "card"; card: ChatCard }
  | { type: "error"; message: string }
  | { type: "done" };
