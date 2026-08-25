import type {
  Entry,
  EntryAccepted,
  Goal,
  Report,
  Tokens,
  User,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STORE_KEY = "progress.tokens";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
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

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  } catch {
    /* fall through to the status text */
  }
  return res.statusText || `Request failed (${res.status})`;
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

  if (!res.ok) throw new ApiError(res.status, await readError(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/* ---------------- auth ---------------- */

export const api = {
  register: (data: {
    email: string;
    password: string;
    display_name?: string;
    timezone: string;
    locale: string;
  }) =>
    request<Tokens>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  login: (email: string, password: string) =>
    request<Tokens>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<User>("/api/auth/me"),

  updateMe: (data: Partial<Pick<User, "display_name" | "timezone" | "cohort">>) =>
    request<User>("/api/auth/me", { method: "PATCH", body: JSON.stringify(data) }),

  /* ---------------- goals ---------------- */

  listGoals: () => request<Goal[]>("/api/goals"),

  createGoal: (data: {
    title: string;
    why_text?: string;
    why_source?: string;
    criteria: { text: string; source: string }[];
  }) => request<Goal>("/api/goals", { method: "POST", body: JSON.stringify(data) }),

  updateGoal: (
    id: string,
    data: {
      title?: string;
      why_text?: string;
      is_active?: boolean;
      criteria?: { text: string; source: string }[];
    },
  ) => request<Goal>(`/api/goals/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  reassignActivity: (activityId: string, goalId: string | null) =>
    request<{ id: string; goal_id: string | null }>(
      `/api/entries/activities/${activityId}`,
      { method: "PATCH", body: JSON.stringify({ goal_id: goalId }) },
    ),

  suggestCriteria: (title: string, why_text?: string) =>
    request<{ criteria: string[] }>("/api/goals/suggest-criteria", {
      method: "POST",
      body: JSON.stringify({ title, why_text }),
    }),

  /* ---------------- entries ---------------- */

  transcribeOnce: (blob: Blob, filename: string) => {
    const form = new FormData();
    form.append("audio", blob, filename);
    return request<{ text: string; seconds: number | null; stt_ms: number }>(
      "/api/entries/transcribe",
      { method: "POST", body: form },
    );
  },

  submitVoice: (blob: Blob, filename: string, goalId?: string, review = true) => {
    const form = new FormData();
    form.append("audio", blob, filename);
    if (goalId) form.append("goal_id", goalId);
    form.append("review", String(review));
    return request<EntryAccepted>("/api/entries/voice", {
      method: "POST",
      body: form,
    });
  },

  confirmTranscript: (id: string, text: string) =>
    request<EntryAccepted>(`/api/entries/${id}/confirm`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  submitText: (text: string, goalId?: string) =>
    request<EntryAccepted>("/api/entries/text", {
      method: "POST",
      body: JSON.stringify({ text, goal_id: goalId ?? null }),
    }),

  getEntry: (id: string) => request<Entry>(`/api/entries/${id}`),

  listEntries: (limit = 60) => request<Entry[]>(`/api/entries?limit=${limit}`),

  retryEntry: (id: string) =>
    request<EntryAccepted>(`/api/entries/${id}/retry`, { method: "POST" }),

  /* ---------------- reports ---------------- */

  generateReport: (body: { goal_id?: string; period_end?: string; force?: boolean } = {}) =>
    request<Report>("/api/reports", { method: "POST", body: JSON.stringify(body) }),

  listReports: () => request<Report[]>("/api/reports"),

  latestReport: () => request<Report>("/api/reports/latest"),

  getReport: (id: string) => request<Report>(`/api/reports/${id}`),

  sendFeedback: (id: string, rating: number, text?: string) =>
    request<Report>(`/api/reports/${id}/feedback`, {
      method: "POST",
      body: JSON.stringify({ rating, text: text || null }),
    }),

  logEvent: (type: string, payload?: Record<string, unknown>) =>
    request<{ ok: boolean }>("/api/events", {
      method: "POST",
      body: JSON.stringify({ type, payload: payload ?? null }),
    }).catch(() => ({ ok: false })),
};

/** Poll a resource until it settles. Processing happens off-request on the server. */
export async function pollUntilSettled<T extends { status: string }>(
  fetcher: () => Promise<T>,
  { intervalMs = 900, timeoutMs = 90_000 } = {},
): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  const inFlight = new Set(["pending", "processing"]);
  let last = await fetcher();
  while (inFlight.has(last.status)) {
    if (Date.now() > deadline) {
      throw new ApiError(408, "This is taking longer than expected. Try again in a moment.");
    }
    await new Promise((r) => setTimeout(r, intervalMs));
    last = await fetcher();
  }
  return last;
}
