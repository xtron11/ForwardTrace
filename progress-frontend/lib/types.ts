/** Types of the v2 API. Shapes follow progress-backend/app/schemas.py. */

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

export type OutreachChannel = "push" | "telegram" | "none";

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
  skill: string | null;
  country: string | null;
  outreach_channel: OutreachChannel;
  telegram_linked: boolean;
  /** The server runs the Telegram bot; without it the channel is not offered. */
  telegram_available: boolean;
  plus_until: string | null;
  first_conversation_done: boolean;
};

export type UserPatch = Partial<
  Pick<
    User,
    | "display_name"
    | "timezone"
    | "locale"
    | "reminder_hour"
    | "reminders_on"
    | "skill"
    | "country"
    | "outreach_channel"
  >
>;

/* ---------------- error codes ---------------- */

/** Every machine code the API can return, as an HTTP error or as an SSE `error` event.
 *  i18n.ts types its table over this list, so a code added here without a translation
 *  does not compile. */
export const ERROR_CODES = [
  "limit_reached",
  "email_not_verified",
  "audio_too_large",
  "unsupported_audio",
  "empty_audio",
  "empty_text",
  "text_too_long",
  "reply_in_progress",
  "not_found",
  "telegram_disabled",
  "bad_range",
  "no_speech",
  "stt_failed",
  "llm_failed",
  "bad_client_msg_id",
] as const;

export type ErrorCode = (typeof ERROR_CODES)[number];

/* ---------------- conversation ---------------- */

export type TextSegment = { type: "text"; text: string };

export type QuoteSegment = {
  type: "quote";
  fact_id: string;
  quote: string;
  local_date: string;
  /** From the first conversation: shown as "from your recollection". */
  recalled?: boolean;
  audio_start_ms?: number | null;
  audio_end_ms?: number | null;
  message_id?: string | null;
};

export type Segment = TextSegment | QuoteSegment;

export type Rating = "helped" | "not_it";

export type Message = {
  id: string;
  role: "user" | "assistant" | string;
  source: string;
  content: Segment[];
  quick_replies: string[] | null;
  intent: string | null;
  rating: Rating | null;
  has_audio: boolean;
  audio_seconds: number | null;
  detected_language: string | null;
  created_at: string;
};

export type Limit = { used: number; free: number; plus: boolean; trial: boolean };

export type Conversation = {
  id: string;
  local_date: string;
  kind: "first" | "daily" | string;
  started_by: string;
  state: Record<string, unknown> | null;
  messages: Message[];
  limit: Limit;
};

export type ThreadBrief = { id: string; title: string; status: string };

export type Day = {
  local_date: string;
  summary: string | null;
  started_by: string;
  threads: ThreadBrief[];
  message_count: number;
};

/** struggle: a difficulty in the skill ("then -> now" pairs come only from these); topic: a theme of life. */
export type ThreadKind = "struggle" | "topic";

export type Thread = {
  id: string;
  title: string;
  kind: ThreadKind;
  status: string;
  opened_on: string;
  closed_on: string | null;
  last_mentioned_on: string | null;
};

export type ThreadPatch = { status?: "closed" | "deleted"; title?: string };

export type Fact = {
  id: string;
  type: string;
  text: string;
  quote: string;
  local_date: string;
  message_id: string | null;
  audio_start_ms: number | null;
  audio_end_ms: number | null;
  flagged: boolean;
};

export type Pair = {
  id: string;
  theme: string;
  recalled: boolean;
  source: string;
  then: Fact;
  now: Fact;
};

export type Criterion = { id: string; text: string; source: string; position: number };

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
  /** null = "no finish line, just grow". */
  finish_line: string | null;
  finish_set_on: string | null;
};

/** PATCH /api/goal. `finish_line: null` means "no finish line". */
export type GoalPatch = { title?: string; why_text?: string; finish_line?: string | null };

export type Memory = {
  goal: Goal | null;
  open_threads: Thread[];
  closed_threads: Thread[];
  facts: Fact[];
};

export type MonthlyContent = {
  intro: Segment[];
  open_struggle: Segment[];
  next_step: Segment[];
};

/** `stats` of a summary: numbers counted by code, the cards (up to 3) and the threads
 *  handled that month, and the motivation quote. Resolved by the server on every read. */
export type MonthlyStats = {
  days: number;
  conversations: number;
  closed_threads: number;
  new_pairs: number;
  level_facts: number;
  pairs: Pair[];
  closed: Thread[];
  why_text: string | null;
};

export type MonthlySummary = {
  /** "YYYY-MM" */
  month: string;
  status: "done" | "thin" | "failed" | string;
  stats: MonthlyStats | null;
  content: MonthlyContent | null;
  viewed_at: string | null;
};

export type Progress = {
  goal: Goal | null;
  level_facts: Fact[];
  pairs: Pair[];
  open_threads: Thread[];
  closed_threads: Thread[];
  monthly: MonthlySummary | null;
};

export type SearchHit = { local_date: string; message_id: string; snippet: string };

export type CalendarDay = { local_date: string; active: boolean };

/* ---------------- stream ---------------- */

/** Events of POST .../messages and .../plateau, in the order they arrive. */
export type StreamEvent =
  | {
      event: "user_message";
      // `content` is null only when a repeat arrives before the voice original was saved.
      data: { id: string; content: string | null; source: string; detected_language: string | null };
    }
  | { event: "delta"; data: { text: string } }
  | { event: "quote"; data: Omit<QuoteSegment, "type"> }
  | {
      event: "done";
      data: {
        /** Null for a repeat whose reply is still being written (`duplicate`). */
        message_id: string | null;
        /** A repeat of a `client_msg_id` already sent: replayed, no new reply. */
        duplicate?: boolean;
        quick_replies: string[] | null;
        used_fact_ids: string[];
        intent: string | null;
      };
    }
  | { event: "error"; data: { code: string; message: string } };

/** Push and reminders keep their v1 shapes. */
export type PushSettings = { reminders_on: boolean; reminder_hour: number };
