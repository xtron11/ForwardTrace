"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useUser } from "@/components/AppShell";
import { ChatThread, type Draft } from "@/components/ChatThread";
import { Composer } from "@/components/Composer";
import { HourPicker } from "@/components/HourPicker";
import { NotifyOffer } from "@/components/NotifyOffer";
import { PaywallSheet } from "@/components/PaywallSheet";
import { WeekStrip } from "@/components/WeekStrip";
import { Button, Notice, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { todayIn } from "@/lib/dates";
import { describeError, errorText } from "@/lib/i18n";
import { newClientMsgId } from "@/lib/ids";
import type { Conversation, Message, Rating, Segment } from "@/lib/types";
import { useT } from "@/lib/useT";

/** A message with its `client_msg_id`: a resend of the same body reuses the id, so the
 *  server answers it with the saved message instead of a second one. Dictated text
 *  carries the id of its recording. */
type Body = { text: string; client_msg_id: string; voice_draft_id?: string };

function textBody(text: string, voiceDraftId: string | null = null): Body {
  return {
    text,
    client_msg_id: newClientMsgId(),
    ...(voiceDraftId ? { voice_draft_id: voiceDraftId } : {}),
  };
}

/**
 * "Today": the week strip and the day's conversation, including the first conversation
 * that replaces onboarding. A reply streams in; afterwards the day is fetched again so
 * every message carries its server id (for ratings and recordings) and the state of
 * the first conversation is current.
 */
export function TodayScreen() {
  const { t } = useT();
  const { user, setUser } = useUser();
  const params = useSearchParams();
  const outreachId = params.get("o");

  const [conv, setConv] = useState<Conversation | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [retryable, setRetryable] = useState(false);
  const [paywall, setPaywall] = useState(false);
  const [pickHour, setPickHour] = useState(false);
  const [offer, setOffer] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [today, setToday] = useState(() => todayIn(user.timezone));

  const busyRef = useRef(false);
  const convRef = useRef<Conversation | null>(null);
  const pending = useRef<Body | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const reported = useRef<string | null>(null);

  const load = useCallback(async () => {
    try {
      const c = await api.todayConversation();
      convRef.current = c;
      setConv(c);
      setLoadFailed(false);
      setToday(todayIn(user.timezone));
    } catch {
      setLoadFailed(true);
    }
  }, [user.timezone]);

  useEffect(() => {
    void load();
  }, [load]);

  // Opened from a push or Telegram link: say so, once.
  useEffect(() => {
    if (!outreachId || reported.current === outreachId) return;
    reported.current = outreachId;
    void api.outreachOpened(outreachId).catch(() => {});
  }, [outreachId]);

  // Coming back to the tab after midnight: it is a new day, so ask for its conversation.
  useEffect(() => {
    function check() {
      if (document.visibilityState !== "visible" || busyRef.current) return;
      const current = convRef.current;
      if (current && todayIn(user.timezone) !== current.local_date) void load();
    }
    document.addEventListener("visibilitychange", check);
    window.addEventListener("focus", check);
    return () => {
      document.removeEventListener("visibilitychange", check);
      window.removeEventListener("focus", check);
    };
  }, [load, user.timezone]);

  const send = useCallback(
    async (body: Body) => {
      // The lock is taken synchronously, before the first await: a second click in the
      // same tick (send button, Enter, a quick reply, the microphone) finds it taken.
      if (busyRef.current) return;
      busyRef.current = true;
      setBusy(true);
      setNotice(null);
      setRetryable(false);
      setPickHour(false);
      pending.current = body;

      const segments: Segment[] = [];
      const snapshot = () => segments.map((s) => ({ ...s }));
      setDraft({ user: body.text, voice: !!body.voice_draft_id, segments: [] });

      let paywalled = false;
      try {
        await api.streamMessage(body, (event, data) => {
          if (event === "user_message") {
            if (data.content != null) setDraft((d) => d && { ...d, user: data.content });
          } else if (event === "delta") {
            const last = segments[segments.length - 1];
            if (last && last.type === "text") last.text += data.text;
            else segments.push({ type: "text", text: data.text });
            setDraft((d) => d && { ...d, segments: snapshot() });
          } else if (event === "quote") {
            segments.push({ type: "quote", ...data });
            setDraft((d) => d && { ...d, segments: snapshot() });
          } else if (event === "error") {
            setNotice(errorText(data.code, t));
          }
        });
      } catch (err) {
        if (err instanceof ApiError && err.code === "limit_reached") {
          paywalled = true;
          setPaywall(true);
        } else {
          setNotice(describeError(err, t));
          setRetryable(true);
        }
      }

      setDraft(null);
      if (!paywalled) {
        const wasOnboarding = !user.first_conversation_done;
        await load();
        setRefreshKey((k) => k + 1);
        if (wasOnboarding) {
          try {
            const me = await api.me();
            if (me.first_conversation_done) {
              setUser(me);
              setOffer(true);
            }
          } catch {
            /* the next load of the app picks it up */
          }
        }
      }
      busyRef.current = false;
      setBusy(false);
    },
    [load, setUser, t, user.first_conversation_done],
  );

  const sendPlateau = useCallback(async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setNotice(null);
    setRetryable(false);
    const segments: Segment[] = [];
    const snapshot = () => segments.map((s) => ({ ...s }));
    setDraft({ user: null, voice: false, segments: [] });
    try {
      await api.streamPlateau((event, data) => {
        if (event === "delta") {
          const last = segments[segments.length - 1];
          if (last && last.type === "text") last.text += data.text;
          else segments.push({ type: "text", text: data.text });
          setDraft((d) => d && { ...d, segments: snapshot() });
        } else if (event === "quote") {
          segments.push({ type: "quote", ...data });
          setDraft((d) => d && { ...d, segments: snapshot() });
        } else if (event === "error") {
          setNotice(errorText(data.code, t));
        }
      });
    } catch (err) {
      setNotice(describeError(err, t));
    }
    setDraft(null);
    await load();
    busyRef.current = false;
    setBusy(false);
  }, [load, t]);

  const dictate = useCallback(
    async (form: FormData) => {
      setNotice(null);
      setRetryable(false);
      try {
        return await api.dictate(form);
      } catch (err) {
        if (err instanceof ApiError && err.code === "limit_reached") setPaywall(true);
        else setNotice(describeError(err, t));
        return null;
      }
    },
    [t],
  );

  const rate = useCallback(
    async (messageId: string, rating: Rating) => {
      setConv((c) =>
        c && { ...c, messages: c.messages.map((m) => (m.id === messageId ? { ...m, rating } : m)) },
      );
      try {
        await api.rateMessage(messageId, rating);
      } catch {
        setConv((c) =>
          c && { ...c, messages: c.messages.map((m) => (m.id === messageId ? { ...m, rating: null } : m)) },
        );
      }
    },
    [],
  );

  if (loadFailed && !conv) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
        <p className="text-dim">{t.today.loadFailed}</p>
        <Button variant="quiet" onClick={() => void load()}>
          {t.shell.retry}
        </Button>
      </div>
    );
  }

  const messages: Message[] = conv?.messages ?? [];
  const last = messages[messages.length - 1];
  const quickReplies = !busy && last?.role === "assistant" ? (last.quick_replies ?? []) : [];
  const state = conv?.state ?? {};
  // "I'll pick a time" is the third reply of the schedule question; it opens a picker
  // instead of being sent as text.
  const choosesHour = state.step === "schedule" && !state.session_end && quickReplies.length === 3;

  function onQuick(text: string, index: number) {
    if (choosesHour && index === 2) setPickHour(true);
    else void send(textBody(text));
  }

  const canRate = (m: Message, i: number) =>
    m.role === "assistant" && conv?.kind !== "first" && messages[i - 1]?.role === "user";

  return (
    <div className="flex flex-1 flex-col">
      <WeekStrip
        today={today}
        refreshKey={refreshKey}
        onToday={() => threadRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
      />

      <div ref={threadRef} className="flex-1 pt-3 pb-4">
        {conv ? (
          <ChatThread
            messages={messages}
            draft={draft}
            quickReplies={quickReplies}
            onQuick={onQuick}
            onRate={(id, rating) => void rate(id, rating)}
            canRate={canRate}
            busy={busy}
          />
        ) : (
          <Spinner label={t.shell.loading} />
        )}

        {user.first_conversation_done && conv && !busy && messages.length > 0 && (
          <div className="mt-5">
            <button
              type="button"
              onClick={() => void sendPlateau()}
              className="press rounded-sm border border-line px-3 py-1.5 text-[length:var(--text-small)] text-muted hover:border-bone hover:text-bone"
            >
              {t.today.plateau}
            </button>
          </div>
        )}

        {offer && (
          <div className="mt-6">
            <NotifyOffer hour={user.reminder_hour} onClose={() => setOffer(false)} />
          </div>
        )}
      </div>

      <div
        className="sticky z-10 flex flex-col gap-2 bg-ink"
        style={{ bottom: "calc(var(--bar-height) + env(safe-area-inset-bottom))" }}
      >
        {notice && (
          <div className="flex flex-wrap items-center gap-3">
            <Notice tone="error">{notice}</Notice>
            {retryable && pending.current && (
              <Button
                variant="link"
                onClick={() => pending.current && void send(pending.current)}
              >
                {t.today.retryLast}
              </Button>
            )}
          </div>
        )}
        {pickHour && (
          <HourPicker
            onClose={() => setPickHour(false)}
            onPick={(hhmm) => {
              setPickHour(false);
              void send(textBody(hhmm));
            }}
          />
        )}
        <Composer
          busy={busy || !conv}
          onSendText={(text, voiceDraftId) => void send(textBody(text, voiceDraftId))}
          onDictate={dictate}
          onProblem={(message) => {
            setNotice(message);
            setRetryable(false);
          }}
        />
      </div>

      <PaywallSheet
        open={paywall}
        onClose={() => setPaywall(false)}
        onGranted={() => {
          setPaywall(false);
          if (pending.current) void send(pending.current);
        }}
      />
    </div>
  );
}
