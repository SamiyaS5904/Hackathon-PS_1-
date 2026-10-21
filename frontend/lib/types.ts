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
}

export interface Session {
  id: string; allotment_id: string; subject_id: string; teacher_id: string; venue_id: string;
  kind: Kind; section_ids: string[]; batch_id: string | null; day: string; shift_id: string;
  start_period: number; length: number; start: string; end: string;
}
export interface Lunch { shift_id: string; year: number; period: number; start: string; end: string }
export interface Timetable {
  college_id: string; status: string; sessions: Session[]; lunches: Lunch[];
  messages: string[]; warnings: string[]; solve_seconds: number;
}
export interface QualityItem { key: string; label: string; value: number; penalty: number; detail: string }
export interface QualityReport {
  score: number; items: QualityItem[];
  teacher_load: Record<string, Record<string, number>>;
  venue_utilisation: Record<string, number>;
}
export interface Violation { type: string; message: string; session_ids: string[] }
export interface TimetableOut { timetable: Timetable; quality: QualityReport | null; violations: Violation[] }
export interface Job { id: string; status: "running" | "done" | "failed"; elapsed: number; error: string | null }
export interface Precheck { problems: string[]; warnings: string[] }

export type ViewKind = "section" | "teacher" | "venue";
