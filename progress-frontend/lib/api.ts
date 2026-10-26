import type {
  AccountDeleted,
  CalendarDay,
  Conversation,
  Day,
  Goal,
  GoalPatch,
  Memory,
  MonthlySummary,
  Progress,
  Rating,
  Registered,
  SearchHit,
  Thread,
  ThreadPatch,
  Tokens,
  User,
  UserPatch,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STORE_KEY = "progress.tokens";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Seconds until a 429 lifts, from the Retry-After header. */
    public retryAfter: number | null = null,
    /** Machine code from `detail.code` (v2 endpoints); null for v1 plain-string errors. */
    public code: string | null = null,
  ) {
    super(message);
  }
}

/** Whole minutes until a 429 lifts. Falls back to the minutes the message names, for
 *  when the header did not make it through a proxy. */
export function retryMinutes(err: ApiError): number {
  if (err.retryAfter) return Math.max(1, Math.ceil(err.retryAfter / 60));
  return Number(/in (\d+) min/.exec(err.message)?.[1]) || 1;
}

/** Retry-After in seconds. The API only ever sends the seconds form, not a date. */
function readRetryAfter(res: Response): number | null {
  const seconds = Number(res.headers.get("Retry-After"));
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

export function loadTokens(): Tokens | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Tokens;
  } catch {
    return null;
  }
}

export function saveTokens(tokens: Tokens): void {
  window.localStorage.setItem(STORE_KEY, JSON.stringify(tokens));
}

export function clearTokens(): void {
  window.localStorage.removeItem(STORE_KEY);
}

export function isSignedIn(): boolean {
  return loadTokens() !== null;
}

async function readError(res: Response): Promise<{ message: string; code: string | null }> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === "string") return { message: detail, code: null };
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      return {
        message: String(detail.message ?? res.statusText),
        code: typeof detail.code === "string" ? detail.code : null,
      };
    }
    if (Array.isArray(detail) && detail[0]?.msg) {
      return { message: String(detail[0].msg), code: null };
    }
  } catch {
    /* fall through to the status text */
  }
  return { message: res.statusText || `Request failed (${res.status})`, code: null };
}

async function failure(res: Response): Promise<ApiError> {
  const { message, code } = await readError(res);
  return new ApiError(res.status, message, readRetryAfter(res), code);
}

/** A single refresh in flight is shared, so parallel 401s don't each rotate tokens. */
let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const current = loadTokens();
  if (!current?.refresh_token) return false;

  refreshing ??= (async () => {
    try {
      const res = await fetch(`${BASE}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: current.refresh_token }),
      });
      if (!res.ok) return false;
      saveTokens((await res.json()) as Tokens);
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();

  return refreshing;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  allowRetry = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  const tokens = loadTokens();
  if (tokens) headers.set("Authorization", `Bearer ${tokens.access_token}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${BASE}${path}`, { ...init, headers });

  if (res.status === 401 && allowRetry && tokens) {
    if (await refreshTokens()) return request<T>(path, init, false);
    clearTokens();
  }

  if (!res.ok) throw await failure(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/* ---------------- server-sent events ---------------- */

export type SseMessage = { event: string; data: unknown };

/**
 * Splits a chunk buffer into complete SSE messages and the unfinished rest.
 * Comment lines (": keepalive") are dropped; several `data:` lines join with a newline.
 */
export function parseSse(buffer: string): { messages: SseMessage[]; rest: string } {
  const blocks = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const rest = blocks.pop() ?? "";
  const messages: SseMessage[] = [];
  for (const block of blocks) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (!line || line.startsWith(":")) continue;
      const colon = line.indexOf(":");
      const field = colon === -1 ? line : line.slice(0, colon);
      const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
      if (field === "event") event = value;
      else if (field === "data") data.push(value);
    }
    if (!data.length) continue;
    const raw = data.join("\n");
    try {
      messages.push({ event, data: JSON.parse(raw) });
    } catch {
      messages.push({ event, data: raw });
    }
  }
  return { messages, rest };
}

type OnEvent = (event: string, data: any) => void; // eslint-disable-line @typescript-eslint/no-explicit-any

/**
 * POST that answers with a text/event-stream (EventSource cannot POST or send a
 * Bearer header). A 401 before the stream starts refreshes the token and repeats the
 * request once; any other refusal before the stream is an ApiError with its `code`.
 * Errors inside the stream arrive as an `error` event, not as an exception.
 */
export async function streamPost(
  path: string,
  body: object | FormData,
  onEvent: OnEvent,
  signal?: AbortSignal,
): Promise<void> {
  const open = async (): Promise<{ res: Response; hadTokens: boolean }> => {
    const headers = new Headers({ Accept: "text/event-stream" });
    const tokens = loadTokens();
    if (tokens) headers.set("Authorization", `Bearer ${tokens.access_token}`);
    let payload: BodyInit;
    if (body instanceof FormData) {
      payload = body;
    } else {
      headers.set("Content-Type", "application/json");
      payload = JSON.stringify(body);
    }
    const res = await fetch(`${BASE}${path}`, { method: "POST", headers, body: payload, signal });
    return { res, hadTokens: tokens !== null };
  };

  let { res, hadTokens } = await open();
  if (res.status === 401 && hadTokens) {
    if (await refreshTokens()) ({ res } = await open());
    else clearTokens();
  }

  if (!res.ok) throw await failure(res);
  if (!res.body) throw new ApiError(res.status, "Empty response");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const parsed = parseSse(done ? buffer + "\n\n" : buffer);
    buffer = parsed.rest;
    for (const m of parsed.messages) onEvent(m.event, m.data);
    if (done) break;
  }
}

/** Authenticated GET returning a blob, for files that sit behind the auth check. */
async function fetchBlob(path: string): Promise<Blob | null> {
  const tokens = loadTokens();
  if (!tokens) return null;
  let res = await fetch(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });
  if (res.status === 401 && (await refreshTokens())) {
    res = await fetch(`${BASE}${path}`, {
      headers: { Authorization: `Bearer ${loadTokens()?.access_token ?? ""}` },
    });
  }
  return res.ok ? await res.blob() : null;
}

const json = (data: unknown) => JSON.stringify(data);

export const api = {
  /* ---------------- auth ---------------- */

  register: (data: {
    email: string;
    password: string;
    display_name?: string;
    timezone: string;
    locale: string;
  }) => request<Tokens | Registered>("/api/auth/register", { method: "POST", body: json(data) }),

  login: (email: string, password: string) =>
    request<Tokens>("/api/auth/login", { method: "POST", body: json({ email, password }) }),

  // Deliberately works signed out: the letter is opened in whatever browser read it.
  verifyEmail: (token: string) =>
    request<{ verified: boolean; email: string }>("/api/auth/verify", {
      method: "POST",
      body: json({ token }),
    }),

  // Unauthenticated: there is no session until the address is confirmed.
  resendVerification: (email: string) =>
    request<{ sent: boolean }>("/api/auth/resend-verification", {
      method: "POST",
      body: json({ email }),
    }),

  me: () => request<User>("/api/auth/me"),

  updateMe: (data: UserPatch) =>
    request<User>("/api/auth/me", { method: "PATCH", body: json(data) }),

  changePassword: (current_password: string, new_password: string) =>
    request<Tokens>("/api/auth/change-password", {
      method: "POST",
      body: json({ current_password, new_password }),
    }),

  logoutEverywhere: () => request<void>("/api/auth/logout-everywhere", { method: "POST" }),

  /** Locks the account and mails a restore link; every session ends, this one included. */
  deleteAccount: () => request<AccountDeleted>("/api/auth/me", { method: "DELETE" }),

  // Unauthenticated, like verifyEmail: a deleted account has no session.
  restoreAccount: (token: string) =>
    request<{ restored: boolean; email: string }>("/api/auth/restore", {
      method: "POST",
      body: json({ token }),
    }),

  /* ---------------- conversations ---------------- */

  todayConversation: () => request<Conversation>("/api/conversations/today"),

  listDays: (before?: string, limit = 30) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (before) q.set("before", before);
    return request<Day[]>(`/api/conversations?${q}`);
  },

  getConversation: (localDate: string) =>
    request<Conversation>(`/api/conversations/${localDate}`),

  deleteConversation: (localDate: string) =>
    request<void>(`/api/conversations/${localDate}`, { method: "DELETE" }),

  /** A person's message: text, or a recording as multipart `audio`. The answer streams. */
  streamMessage: (body: { text: string } | FormData, onEvent: OnEvent, signal?: AbortSignal) =>
    streamPost("/api/conversations/today/messages", body, onEvent, signal),

  /** "It seems I am standing still": the assistant answers alone. */
  streamPlateau: (onEvent: OnEvent, signal?: AbortSignal) =>
    streamPost("/api/conversations/today/plateau", {}, onEvent, signal),

  search: (q: string) => request<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}`),

  calendar: (from: string, to: string) =>
    request<CalendarDay[]>(`/api/calendar?from=${from}&to=${to}`),

  /** Authenticated, so it cannot be a plain <audio src>: fetched as a blob object URL. */
  messageAudioUrl: async (messageId: string): Promise<string | null> => {
    const blob = await fetchBlob(`/api/messages/${messageId}/audio`);
    return blob ? URL.createObjectURL(blob) : null;
  },

  rateMessage: (messageId: string, rating: Rating) =>
    request<void>(`/api/messages/${messageId}/rating`, {
      method: "POST",
      body: json({ rating }),
    }),

  flagFact: (factId: string) => request<void>(`/api/facts/${factId}/flag`, { method: "POST" }),

  updateThread: (id: string, data: ThreadPatch) =>
    request<Thread>(`/api/threads/${id}`, { method: "PATCH", body: json(data) }),

  memory: () => request<Memory>("/api/memory"),

  /* ---------------- progress ---------------- */

  progress: () => request<Progress>("/api/progress"),

  monthly: (month: string) =>
    request<MonthlySummary>(`/api/progress/monthly?month=${encodeURIComponent(month)}`),

  hidePair: (id: string) => request<void>(`/api/pairs/${id}/hide`, { method: "POST" }),

  patchGoal: (data: GoalPatch) =>
    request<Goal>("/api/goal", { method: "PATCH", body: json(data) }),

  /* ---------------- account, channels ---------------- */

  paywallClick: () => request<{ plus_until: string }>("/api/paywall/click", { method: "POST" }),

  telegramLink: () => request<{ url: string }>("/api/telegram/link", { method: "POST" }),

  /** Not built yet on the server (ticket 07 owns it); the button that calls this only
   *  shows once `telegram_linked` is true, which cannot happen before that. */
  telegramUnlink: () => request<void>("/api/telegram/link", { method: "DELETE" }),

  /** JSON export of everything the person said; the caller saves it as a file. */
  exportData: (): Promise<Blob | null> => fetchBlob("/api/me/export"),

  /** Opened from a push or Telegram link (/today?o=<id>). Idempotent. */
  outreachOpened: (id: string) =>
    request<void>(`/api/outreach/${id}/opened`, { method: "POST" }),

  pushKey: () => request<{ key: string; enabled: boolean }>("/api/push/key"),

  pushSubscribe: (subscription: { endpoint: string; keys: { p256dh: string; auth: string } }) =>
    request<{ ok: boolean }>("/api/push/subscribe", {
      method: "POST",
      body: json(subscription),
    }),

  pushUnsubscribe: (endpoint: string) =>
    request<void>("/api/push/unsubscribe", { method: "POST", body: json({ endpoint }) }),

  updateReminderSettings: (data: { reminders_on?: boolean; reminder_hour?: number }) =>
    request<{ reminders_on: boolean; reminder_hour: number }>("/api/push/settings", {
      method: "PATCH",
      body: json(data),
    }),

  pushTest: () => request<{ delivered: number }>("/api/push/test", { method: "POST" }),

  logEvent: (type: string, payload?: Record<string, unknown>) =>
    request<{ ok: boolean }>("/api/events", {
      method: "POST",
      body: json({ type, payload: payload ?? null }),
    }).catch(() => ({ ok: false })),
};
