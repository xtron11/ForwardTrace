/**
 * Localisation.
 *
 * Before sign-in the language follows the browser; after sign-in it is `users.locale`
 * (see useT.ts, which holds the active locale). There is no locale in the URL.
 *
 * Russian copy addresses the person as "вы" and avoids verb forms that carry gender
 * ("вы прошли", not "ты прошёл"). Every key must exist in both dictionaries: `ru` is
 * typed as the shape of `en`.
 */

import { ApiError } from "./api";
import { plural } from "./dates";
import { ERROR_CODES, type ErrorCode } from "./types";

export type Locale = "en" | "ru";

export function detectLocale(): Locale {
  if (typeof navigator === "undefined") return "en";
  const tags = navigator.languages?.length ? navigator.languages : [navigator.language];
  return tags.some((tag) => tag?.toLowerCase().startsWith("ru")) ? "ru" : "en";
}

/** Maps a stored `users.locale` ("ru", "en", "ru-RU"…) onto a supported locale. */
export function toLocale(value: string | null | undefined): Locale {
  return value?.toLowerCase().startsWith("ru") ? "ru" : "en";
}

/** через 1 минуту, 2 минуты, 5 минут, 21 минуту. */
function ruMinutes(n: number): string {
  const tens = n % 100;
  const ones = n % 10;
  if (tens >= 11 && tens <= 14) return `${n} минут`;
  if (ones === 1) return `${n} минуту`;
  if (ones >= 2 && ones <= 4) return `${n} минуты`;
  return `${n} минут`;
}

/** One line per API code. Typed over ERROR_CODES: a code added there without a
 *  translation does not compile, and `ru` must have the same keys. */
const enErrorCodes: Record<ErrorCode, string> = {
  limit_reached: "This week's free conversations are used up. Continue with Plus.",
  email_not_verified: "Confirm your email first — the link is in the letter we sent.",
  audio_too_large: "The recording is too large. Try a shorter one, or type instead.",
  unsupported_audio: "This recording format is not supported. Type instead.",
  empty_audio: "The recording is empty. Try again.",
  empty_text: "The message is empty.",
  text_too_long: "The message is too long. Shorten it or split it into parts.",
  reply_in_progress: "A reply is still being written. Wait for it to finish.",
  not_found: "Not found.",
  telegram_disabled: "Telegram is not available right now.",
  bad_range: "That date range is not valid.",
  no_speech: "No speech was heard in that recording. Try again, or type instead.",
  stt_failed: "The recording could not be transcribed. Try again, or type instead.",
  llm_failed: "No reply could be produced. Try again in a little while.",
};

const en = {
  brand: "ForwardTrace",

  /** Browser tab titles: "Today · ForwardTrace". */
  pageTitles: {
    today: "Today",
    history: "History",
    progress: "Progress",
    profile: "Profile",
    signIn: "Sign in",
    register: "Create an account",
    restore: "Account recovery",
    verify: "Confirmation",
  },

  nav: {
    today: "Today",
    history: "History",
    progress: "Progress",
    profile: "Profile",
    settings: "Settings",
    signOut: "Sign out",
    primary: "Main navigation",
  },

  shell: {
    loading: "Loading…",
    retry: "Retry",
    themeLight: "Light theme",
    themeDark: "Dark theme",
  },

  auth: {
    createTitle: "Create an account",
    createLede: "Your conversations and what they remember are kept under this account.",
    signInTitle: "Sign in",
    email: "Email",
    password: "Password",
    passwordHint: "At least 8 characters.",
    name: "Name",
    nameHint: "Optional — how you would like to be addressed.",
    create: "Create account",
    creating: "Creating…",
    signIn: "Sign in",
    signingIn: "Signing in…",
    noAccount: "No account yet?",
    createOne: "Create one",
    alreadyHave: "Already have one?",
    signInLink: "Sign in",
    createFailed: "Could not create the account.",
    emailTaken: "An account with this email already exists. Sign in instead.",
    signInFailed: "Could not sign in. Check the email and password.",
    tooManyAttempts: (minutes: number) =>
      `Too many attempts. Try again in ${minutes} ${minutes === 1 ? "minute" : "minutes"}.`,
  },

  verify: {
    checking: "CONFIRMING",
    okTitle: "Address confirmed",
    okBody: "You can sign in now.",
    okCta: "SIGN IN",
    failTitle: "This link doesn't work",
    failBody: "It may have expired, or a newer one was sent. Sign in and ask for another.",
    failCta: "SIGN IN",
    pendingLabel: "CHECK YOUR EMAIL",
    pendingBody: "We sent a letter to {email}. Follow the link in it, then sign in.",
    notConfirmed: "This address is not confirmed yet. Check the letter we sent.",
    resend: "send it again",
    resent: "Sent. Check the letter, and the spam folder.",
  },

  restore: {
    checking: "RESTORING",
    okTitle: "Account restored",
    okBody: "Everything is where you left it. You can sign in now.",
    okCta: "SIGN IN",
    failTitle: "This link doesn't work",
    failBody:
      "The restore period may be over, or a newer letter was sent. Try signing in: if the account can still be restored, we'll send a fresh link.",
    failCta: "SIGN IN",
    deletedOnLogin:
      "This account has been deleted. To sign in, restore it from the letter we've sent to your email.",
  },

  notFound: {
    label: "404",
    title: "Nothing here",
    body: "The link may be old, or the address has a typo.",
    ctaHome: "TO THE HOME PAGE",
    ctaToday: "TO TODAY",
  },


  audio: {
    play: "Play",
    stop: "Stop",
    seconds: (n: number) => `${n} s`,
  },

  errors: {
    generic: "Something went wrong. Try again.",
    offline: "No connection to the server. Check the network and try again.",
    micBlocked: "Microphone access is blocked. Allow it in your browser, or type instead.",
    noRecorder: "This browser can't record audio. You can type instead.",
    silent:
      "That recording came through silent — your browser is probably listening to the wrong microphone. Check the padlock in the address bar, or type instead.",
  },

  today: {
    weekStrip: "Week",
    prevWeek: "Previous week",
    nextWeek: "Next week",
    emptyDay: "There was no conversation on this day",
    loadFailed: "The conversation could not be loaded.",
    inputPlaceholder: "Write a message…",
    send: "Send",
    record: "Record a voice message",
    stopAndSend: "Stop and send",
    cancelRecording: "Discard the recording",
    recording: "Recording",
    sendingVoice: "Voice message",
    thinking: "Writing a reply…",
    plateau: "I think I'm standing still",
    helped: "Helped",
    notIt: "Not it",
    rated: "Thank you, noted.",
    inaccurate: "This is not accurate",
    inaccurateDone: "Noted. This quote will not be used again.",
    quoteActions: "Quote actions",
    recalled: "from your recollection",
    openDay: "Open this day",
    you: "You",
    assistant: "ForwardTrace",
    pickHour: "Pick an hour",
    pickHourLabel: "Hour for the daily message",
    retryLast: "Try again",
  },

  notify: {
    title: "A message at the chosen hour",
    body: "Allow notifications so the message arrives on time.",
    allow: "Allow notifications",
    later: "Not now",
    done: (hour: number) => `Done. The message will come around ${String(hour).padStart(2, "0")}:00.`,
    failed: "Notifications were not turned on.",
    iosInstall:
      "On iPhone notifications work after the app is added to the Home Screen (Share → Add to Home Screen).",
    telegramTitle: "Telegram instead",
    telegramBody: "You can get the daily message in Telegram.",
    telegramCta: "Connect Telegram",
    laterInProfile: "You can change this any time in Profile.",
  },

  paywall: {
    title: "Continue with Plus",
    body: "This week's free conversations are used up. Plus means unlimited conversations — nothing else changes: memory, quotes and \"I think I'm standing still\" stay free for everyone.",
    resets: "The free conversations of this week return on Monday.",
    cta: "Continue with Plus",
    working: "One moment…",
    beta: "We're in beta — you get a month free",
    granted: (date: string) => `Unlimited conversations until ${date}.`,
    close: "Close",
  },

  history: {
    title: "History",
    searchPlaceholder: "Search your messages",
    searchLabel: "Search",
    empty: "Talk today — the day will appear here.",
    emptyCta: "To today",
    noResults: "Nothing found.",
    more: "Show more",
    messages: (n: number) => `${n} ${n === 1 ? "message" : "messages"}`,
    startedByAi: "The assistant wrote first",
    notFound: "No conversation was found for this day.",
    back: "To history",
    voice: "Voice message",
    delete: "Delete this conversation",
    deleteAsk:
      "Delete this conversation together with its recordings and what was remembered from it? This cannot be undone.",
    deleteYes: "Delete",
    deleteNo: "Cancel",
    deleting: "Deleting…",
    openThread: "open",
    closedThread: "closed",
  },

  profile: {
    title: "Profile",
    account: "Account",
    goal: "Goal",
    goalTitle: "What you are developing",
    goalWhy: "Why it matters to you",
    goalFinish: "Finish line",
    noFinish: "No finish line — just growing",
    noFinishToggle: "No finish line — I just want to grow",
    noGoal: "The goal appears after the first conversation.",
    edit: "Edit",
    save: "Save",
    saving: "Saving…",
    cancel: "Cancel",
    saved: "Saved.",
    messages: "Messages from the assistant",
    hour: "Hour",
    channel: "Where to write",
    channelPush: "Notifications",
    channelTelegram: "Telegram",
    channelNone: "Do not write first",
    telegramConnect: "Connect Telegram",
    telegramLinked: "Telegram is connected.",
    telegramUnlink: "Disconnect Telegram",
    telegramHint: "The link opens the bot; press Start there.",
    appearance: "Appearance",
    language: "Language",
    theme: "Theme",
    install: "Install the app",
    installed: "The app is installed.",
    installManual: "On iPhone: Share → Add to Home Screen.",
    data: "Your data",
    export: "Download my data (JSON)",
    exporting: "Preparing…",
    deleteAccount: "Delete account",
    deleteAsk:
      "Delete the account? It is locked now and erased for good after the restore period; a restore link goes to your email.",
    deleteYes: "Delete the account",
    deleteNo: "Cancel",
    signOut: "Sign out",
  },

  progress: {
    title: "Progress",
    goal: "Goal",
    why: "Why",
    finish: "Finish line",
    noFinish: "No finish line — just growing",
    noGoal: "Your goal appears after the first conversation.",
    path: "Where you are",
    pathEmpty: "Tell me where you are relative to the finish line.",
    pairs: "Before and after",
    pairsEmpty:
      "Before-and-after cards will appear once at least a week has passed between a difficulty and a success.",
    then: "Then",
    now: "Now",
    hide: "Hide",
    hideLabel: "Hide this card",
    threads: "Difficulties",
    threadsOpen: "Open",
    threadsClosed: "Handled",
    threadsEmpty: "Difficulties you mention will be followed here until you say you have handled them.",
    threadsNone: "None",
    closeThread: "Mark as handled",
    deleteThread: "Delete",
    closedOn: (date: string) => `handled ${date}`,
    changeFailed: "Could not save the change. Try again.",
    monthly: {
      title: (month: string) => `Summary for ${month}`,
      thin: (month: string) => `Not much data for ${month} — here's what there is`,
      open: "Read",
      days: "Days with a conversation",
      closedThreads: "Difficulties handled",
      newPairs: "New before-and-after cards",
      cards: "Before and after",
      closed: "Handled this month",
      openStruggle: "Still open",
      motivation: "Why you started",
      nextStep: "A small next step",
      failed: "This summary could not be written.",
      notFound: "There is no summary for this month.",
      back: "Progress",
    },
  },

  errorCodes: enErrorCodes,
};

/** Shape only. Without widening, every English string would be its own literal type
 *  and no translation could ever satisfy it. */
type Dict = typeof en;

const ru: Dict = {
  brand: "ForwardTrace",

  pageTitles: {
    today: "Сегодня",
    history: "История",
    progress: "Прогресс",
    profile: "Профиль",
    signIn: "Вход",
    register: "Создание аккаунта",
    restore: "Восстановление аккаунта",
    verify: "Подтверждение",
  },

  nav: {
    today: "Сегодня",
    history: "История",
    progress: "Прогресс",
    profile: "Профиль",
    settings: "Настройки",
    signOut: "Выйти",
    primary: "Основная навигация",
  },

  shell: {
    loading: "Загрузка…",
    retry: "Повторить",
    themeLight: "Светлая тема",
    themeDark: "Тёмная тема",
  },

  auth: {
    createTitle: "Создать аккаунт",
    createLede: "Ваши разговоры и то, что из них запоминается, хранятся под этим аккаунтом.",
    signInTitle: "Вход",
    email: "Почта",
    password: "Пароль",
    passwordHint: "Минимум 8 символов.",
    name: "Имя",
    nameHint: "Необязательно — так к вам будут обращаться.",
    create: "Создать аккаунт",
    creating: "Создаём…",
    signIn: "Войти",
    signingIn: "Входим…",
    noAccount: "Ещё нет аккаунта?",
    createOne: "Создать",
    alreadyHave: "Уже есть аккаунт?",
    signInLink: "Войти",
    createFailed: "Не удалось создать аккаунт.",
    emailTaken: "Аккаунт с этой почтой уже есть. Войдите в него.",
    signInFailed: "Не удалось войти. Проверьте почту и пароль.",
    tooManyAttempts: (minutes: number) =>
      `Слишком много попыток. Повторите через ${ruMinutes(minutes)}.`,
  },

  verify: {
    checking: "ПОДТВЕРЖДАЕМ",
    okTitle: "Адрес подтверждён",
    okBody: "Теперь можно войти.",
    okCta: "ВОЙТИ",
    failTitle: "Ссылка не работает",
    failBody: "Возможно, она устарела или было отправлено новое письмо. Войдите и запросите ещё одно.",
    failCta: "ВОЙТИ",
    pendingLabel: "ПРОВЕРЬТЕ ПОЧТУ",
    pendingBody: "Мы отправили письмо на {email}. Перейдите по ссылке из него, а затем войдите.",
    notConfirmed: "Этот адрес ещё не подтверждён. Проверьте письмо, которое мы отправили.",
    resend: "отправить ещё раз",
    resent: "Отправлено. Проверьте письмо и папку «Спам».",
  },

  restore: {
    checking: "ВОССТАНАВЛИВАЕМ",
    okTitle: "Аккаунт восстановлен",
    okBody: "Все данные на месте. Теперь можно войти.",
    okCta: "ВОЙТИ",
    failTitle: "Ссылка не работает",
    failBody:
      "Возможно, срок восстановления истёк или было отправлено более новое письмо. Попробуйте войти: если аккаунт ещё можно восстановить, мы пришлём новую ссылку.",
    failCta: "ВОЙТИ",
    deletedOnLogin:
      "Этот аккаунт был удалён. Чтобы войти, восстановите его по ссылке из письма — мы отправили его на вашу почту.",
  },

  notFound: {
    label: "404",
    title: "Здесь ничего нет",
    body: "Возможно, ссылка устарела или в адресе опечатка.",
    ctaHome: "НА ГЛАВНУЮ",
    ctaToday: "К СЕГОДНЯ",
  },


  audio: {
    play: "Слушать",
    stop: "Стоп",
    seconds: (n: number) => `${n} с`,
  },

  errors: {
    generic: "Что-то пошло не так. Попробуйте ещё раз.",
    offline: "Нет связи с сервером. Проверьте сеть и попробуйте ещё раз.",
    micBlocked: "Доступ к микрофону заблокирован. Разрешите его в браузере или напишите текстом.",
    noRecorder: "Этот браузер не умеет записывать звук. Можно написать текстом.",
    silent:
      "Запись получилась беззвучной — скорее всего, браузер слушает не тот микрофон. Проверьте значок замка в адресной строке или напишите текстом.",
  },

  today: {
    weekStrip: "Неделя",
    prevWeek: "Предыдущая неделя",
    nextWeek: "Следующая неделя",
    emptyDay: "В этот день разговора не было",
    loadFailed: "Не удалось загрузить разговор.",
    inputPlaceholder: "Напишите сообщение…",
    send: "Отправить",
    record: "Записать голосовое сообщение",
    stopAndSend: "Остановить и отправить",
    cancelRecording: "Отменить запись",
    recording: "Идёт запись",
    sendingVoice: "Голосовое сообщение",
    thinking: "Пишу ответ…",
    plateau: "Кажется, я стою на месте",
    helped: "Помогло",
    notIt: "Не то",
    rated: "Спасибо, учтено.",
    inaccurate: "Это неточно",
    inaccurateDone: "Учтено. Эта цитата больше не будет использоваться.",
    quoteActions: "Действия с цитатой",
    recalled: "по вашим воспоминаниям",
    openDay: "Открыть этот день",
    you: "Вы",
    assistant: "ForwardTrace",
    pickHour: "Выберите час",
    pickHourLabel: "Час ежедневного сообщения",
    retryLast: "Повторить",
  },

  notify: {
    title: "Сообщение в выбранный час",
    body: "Разрешите уведомления, чтобы сообщение приходило вовремя.",
    allow: "Разрешить уведомления",
    later: "Не сейчас",
    done: (hour: number) => `Готово. Сообщение придёт около ${String(hour).padStart(2, "0")}:00.`,
    failed: "Уведомления не включились.",
    iosInstall:
      "На iPhone уведомления работают после добавления приложения на экран «Домой» (Поделиться → На экран «Домой»).",
    telegramTitle: "Можно через Telegram",
    telegramBody: "Ежедневное сообщение можно получать в Telegram.",
    telegramCta: "Подключить Telegram",
    laterInProfile: "Это можно изменить в любой момент в профиле.",
  },

  paywall: {
    title: "Продолжить с Plus",
    body: "Бесплатные разговоры этой недели закончились. Plus — это безлимитные разговоры, и только: память, цитаты и «Кажется, я стою на месте» остаются доступны всем.",
    resets: "Бесплатные разговоры этой недели вернутся в понедельник.",
    cta: "Продолжить с Plus",
    working: "Секунду…",
    beta: "Мы в бете — вам месяц бесплатно",
    granted: (date: string) => `Безлимитные разговоры до ${date}.`,
    close: "Закрыть",
  },

  history: {
    title: "История",
    searchPlaceholder: "Поиск по вашим сообщениям",
    searchLabel: "Поиск",
    empty: "Поговорите сегодня — день появится здесь.",
    emptyCta: "К сегодняшнему дню",
    noResults: "Ничего не нашлось.",
    more: "Показать ещё",
    messages: (n: number) =>
      `${n} ${plural("ru", n, { one: "сообщение", few: "сообщения", many: "сообщений" })}`,
    startedByAi: "Первым написал ИИ",
    notFound: "Разговор за этот день не найден.",
    back: "К истории",
    voice: "Голосовое сообщение",
    delete: "Удалить разговор",
    deleteAsk:
      "Удалить этот разговор вместе с записями и тем, что из него запомнилось? Это нельзя отменить.",
    deleteYes: "Удалить",
    deleteNo: "Отмена",
    deleting: "Удаляем…",
    openThread: "открыта",
    closedThread: "закрыта",
  },

  profile: {
    title: "Профиль",
    account: "Аккаунт",
    goal: "Цель",
    goalTitle: "Что вы развиваете",
    goalWhy: "Зачем это вам",
    goalFinish: "Финиш",
    noFinish: "Без финиша — расту",
    noFinishToggle: "Без финиша — хочу просто расти",
    noGoal: "Цель появится после первого разговора.",
    edit: "Изменить",
    save: "Сохранить",
    saving: "Сохраняем…",
    cancel: "Отмена",
    saved: "Сохранено.",
    messages: "Сообщения от ИИ",
    hour: "Час",
    channel: "Куда писать",
    channelPush: "Уведомления",
    channelTelegram: "Telegram",
    channelNone: "Первым не писать",
    telegramConnect: "Подключить Telegram",
    telegramLinked: "Telegram подключён.",
    telegramUnlink: "Отвязать Telegram",
    telegramHint: "Ссылка откроет бота — нажмите там «Start».",
    appearance: "Оформление",
    language: "Язык",
    theme: "Тема",
    install: "Установить приложение",
    installed: "Приложение установлено.",
    installManual: "На iPhone: Поделиться → На экран «Домой».",
    data: "Ваши данные",
    export: "Скачать мои данные (JSON)",
    exporting: "Готовим…",
    deleteAccount: "Удалить аккаунт",
    deleteAsk:
      "Удалить аккаунт? Он будет заблокирован, а после периода восстановления удалён насовсем; ссылка для восстановления придёт на вашу почту.",
    deleteYes: "Удалить аккаунт",
    deleteNo: "Отмена",
    signOut: "Выйти",
  },

  progress: {
    title: "Прогресс",
    goal: "Цель",
    why: "Зачем",
    finish: "Финиш",
    noFinish: "Без финиша — расту",
    noGoal: "Цель появится после первого разговора.",
    path: "Где вы сейчас",
    pathEmpty: "Расскажите, где вы сейчас относительно финиша",
    pairs: "Было → стало",
    pairsEmpty:
      "Карточки «было → стало» появятся, когда пройдёт хотя бы неделя между трудностью и успехом",
    then: "Было",
    now: "Стало",
    hide: "Скрыть",
    hideLabel: "Скрыть эту карточку",
    threads: "Трудности",
    threadsOpen: "Открытые",
    threadsClosed: "Преодолённые",
    threadsEmpty: "Трудности, о которых вы расскажете, будут здесь, пока вы не скажете, что справились.",
    threadsNone: "Нет",
    closeThread: "Отметить как преодолённую",
    deleteThread: "Удалить",
    closedOn: (date: string) => `закрыта ${date}`,
    changeFailed: "Не удалось сохранить изменение. Повторите попытку.",
    monthly: {
      title: (month: string) => `Сводка за ${month}`,
      thin: (month: string) => `Мало данных за ${month} — вот что есть`,
      open: "Читать",
      days: "Дней с разговором",
      closedThreads: "Преодолено трудностей",
      newPairs: "Новых карточек «было → стало»",
      cards: "Было → стало",
      closed: "Преодолено в этом месяце",
      openStruggle: "Пока не решено",
      motivation: "Зачем вы начали",
      nextStep: "Один небольшой шаг",
      failed: "Эту сводку не удалось подготовить.",
      notFound: "За этот месяц сводки нет.",
      back: "Прогресс",
    },
  },

  errorCodes: {
    limit_reached: "Бесплатные разговоры этой недели закончились. Продолжить можно с Plus.",
    email_not_verified: "Сначала подтвердите почту — ссылка в письме, которое мы отправили.",
    audio_too_large: "Запись слишком большая. Попробуйте покороче или напишите текстом.",
    unsupported_audio: "Этот формат записи не поддерживается. Напишите текстом.",
    empty_audio: "Запись пустая. Попробуйте ещё раз.",
    empty_text: "Сообщение пустое.",
    text_too_long: "Сообщение слишком длинное. Сократите его или разбейте на части.",
    reply_in_progress: "Ответ ещё пишется — дождитесь, пока он закончится.",
    not_found: "Не найдено.",
    telegram_disabled: "Telegram сейчас недоступен.",
    bad_range: "Неверный диапазон дат.",
    no_speech: "В записи не слышно речи. Попробуйте ещё раз или напишите текстом.",
    stt_failed: "Не удалось распознать запись. Попробуйте ещё раз или напишите текстом.",
    llm_failed: "Не удалось получить ответ. Повторите чуть позже.",
  },
};

const DICTS: Record<Locale, Dict> = { en, ru };

export function dict(locale: Locale): Dict {
  return DICTS[locale];
}

/** Text for an API error code. Unknown or missing codes give the generic line. */
export function errorText(code: string | null | undefined, t: Dict): string {
  if (code && (ERROR_CODES as readonly string[]).includes(code)) {
    return t.errorCodes[code as ErrorCode];
  }
  return t.errors.generic;
}

/**
 * What to show for a failed request. v2 endpoints carry a `code` and are translated by
 * it. v1 endpoints (auth, push) send English strings, which are never shown: the only
 * code-less conflict (409) is registration with a taken address, and it gets its own
 * line; anything else gets the generic one.
 */
export function describeError(err: unknown, t: Dict): string {
  if (!(err instanceof ApiError)) return t.errors.offline;
  if (err.code) return errorText(err.code, t);
  if (err.status === 409) return t.auth.emailTaken;
  return t.errors.generic;
}
