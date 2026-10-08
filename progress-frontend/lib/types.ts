/** Registration returns one or the other: a session when there is no mail provider,
 *  otherwise a request to go and confirm the address. */
export type Registered = { verification_required: true; email: string };

export type AccountDeleted = {
  email: string;
  /** ISO date: the day the data is erased for good. */
  erase_on: string;
  restore_days: number;
  letter_sent: boolean;
};

export type Tokens = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

export type User = {
  id: string;
  email: string;
  display_name: string | null;
  timezone: string;
  locale: string;
  email_verified: boolean;
  cohort: string | null;
  reminder_hour: number;
  reminders_on: boolean;
  intake: Record<string, unknown> | null;
  created_at: string;
};

export type Criterion = {
  id: string;
  text: string;
  source: string;
  position: number;
};

export type Goal = {
  id: string;
  title: string;
  why_text: string | null;
  why_source: string;
  why_audio_seconds: number | null;
  is_active: boolean;
  started_on: string | null;
  created_at: string;
  criteria: Criterion[];
};

export type Metric = {
  name: string;
  value: number;
  unit: string;
  quote: string;
};

export type Activity = {
  id: string;
  /** Which goal the extractor routed this to. Null when it fits none of them. */
  goal_id: string | null;
  category: string;
  minutes: number | null;
  minutes_explicit: boolean;
  details: string[] | null;
  /** Countable quantities the person stated, e.g. 10 new words. */
  metrics: Metric[] | null;
  /** Verbatim span from the transcript. The only text allowed a highlighter. */
  quote: string | null;
};

export type Fact = { text: string; quote: string; goal_id: string | null };

export type HorizonDay = {
  date: string;
  has_entry: boolean;
  /** 0..1 against the fullest day in view. Never a fraction of a target - there is no
   *  target, so a quiet day cannot read as a shortfall. */
  weight: number;
};

export type AccumulatedMetric = {
  name: string;
  unit: string;
  total: number;
  occasions: number;
};

export type PersonalRecord = {
  name: string;
  unit: string;
  value: number;
  previous_best: number;
};

/** Absent fields mean "nothing to say", never "you fell short". */
export type DailySummary = {
  days_in_journey: number;
  checked_in_today: boolean;
  horizon: HorizonDay[];
  accumulated: AccumulatedMetric | null;
  personal_record: PersonalRecord | null;
  days_until_report: number | null;
  goal_title: string | null;
  goal_id: string | null;
  has_completed_period: boolean;
};

export type TaskEvidence = { date: string; quote: string | null };

/** An intention, compared against what was actually said.
 *  Note the absence of any completed flag: days_touched against span_days is the whole
 *  story, and the person draws their own conclusion from it. */
export type Task = {
  id: string;
  text: string;
  status: "active" | "closed";
  source: string;
  starts_on: string;
  ends_on: string;
  span_days: number;
  days_touched: number;
  evidence: TaskEvidence[];
};

export type TaskSuggestions = {
  should_ask: boolean;
  suggestions: string[];
};

/** A paragraph of the answer shown after a check-in. `reference` is present only when
 *  the paragraph makes a claim about the past, and it has already been checked against
 *  the entry from that date. */
export type ReflectionParagraph = {
  text: string;
  reference: { date: string; quote: string } | null;
};

export type EntryStatus =
  | "pending"
  | "processing"
  /** Transcript is ready; waiting for the person to confirm or correct it. */
  | "awaiting_review"
  | "done"
  | "failed";

export type Entry = {
  id: string;
  goal_id: string | null;
  local_date: string;
  source: string;
  status: EntryStatus;
  audio_seconds: number | null;
  /** Whether the recording is still on disk and can be played back. */
  has_audio: boolean;
  raw_transcript: string | null;
  stt_transcript: string | null;
  transcript_edited: boolean;
  mood: string | null;
  wins: Fact[] | null;
  friction: Fact[] | null;
  reflection: ReflectionParagraph[] | null;
  error: string | null;
  stt_ms: number | null;
  llm_ms: number | null;
  dropped_facts: number;
  created_at: string;
  activities: Activity[];
};

export type EntryAccepted = {
  id: string;
  status: EntryStatus;
  local_date: string;
  poll_url: string;
};

export type CategoryStat = {
  category: string;
  total_minutes: number;
  total_human: string;
  sessions: number;
  days_active: number;
  sessions_with_time: number;
  time_coverage: number;
};

export type MetricTotal = {
  name: string;
  unit: string;
  total: number;
  occasions: number;
};

export type MonthlyDigest = {
  year: number;
  month: number;
  period_start: string;
  period_end: string;
  goal_title: string | null;
  goal_why: string | null;
  days_logged: number;
  days_in_month: number;
  entries: number;
  metrics: { name: string; unit: string; total: number }[];
  strongest_day: { date: string; minutes: number; quote: string | null } | null;
  changes: { text: string; evidence: string }[];
  then: { date: string; said: string | null } | null;
  now: { date: string; said: string | null } | null;
  /** Too little in the month to dress up as a retrospective. */
  thin: boolean;
};

export type ReportStats = {
  /** Goal as it stood when the report was written, not as it is now. */
  goal_title?: string;
  goal_why?: string | null;
  criteria_snapshot?: string[];
  criteria_changed_midperiod?: boolean;
  /** First report of a goal: three days, not a full week. */
  is_first_report?: boolean;
  period_start: string;
  period_end: string;
  period_days: number;
  days_logged: number;
  entries: number;
  longest_streak: number;
  total_minutes: number;
  total_human: string;
  categories: CategoryStat[];
  metrics?: MetricTotal[];
  wins: string[];
  friction: string[];
};

export type CriterionProgress = {
  criterion_id: string;
  status: "no_evidence" | "some_evidence" | "clear_evidence";
  evidence: string;
};

export type ReportContent = {
  what_you_did: string;
  what_changed: { text: string; evidence: string }[];
  pattern: { text: string; confidence: "low" | "medium" | "high" };
  friction: string;
  recommendation: string;
  closing: string;
  criteria_progress: CriterionProgress[];
  criteria_labels: Record<string, string>;
};

export type Report = {
  id: string;
  goal_id: string | null;
  period_start: string;
  period_end: string;
  status: EntryStatus;
  stats: ReportStats | null;
  content: ReportContent | null;
  generated_by: string;
  error: string | null;
  feedback_rating: number | null;
  feedback_text: string | null;
  created_at: string;
};
