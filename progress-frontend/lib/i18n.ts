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

  /** Screens that the next ticket fills in. */
  placeholder: {
    today: "Today's conversation will appear here.",
    history: "Your days will appear here.",
    historyDay: "This day's conversation will appear here.",
    progress: "Your progress will appear here.",
    profile: "Settings will appear here.",
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

  errorCodes: enErrorCodes,
};

/** Shape only. Without widening, every English string would be its own literal type
 *  and no translation could ever satisfy it. */
type Dict = typeof en;

const ru: Dict = {
  brand: "ForwardTrace",

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

  placeholder: {
    today: "Здесь появится разговор дня.",
    history: "Здесь появятся ваши дни.",
    historyDay: "Здесь появится разговор этого дня.",
    progress: "Здесь появится ваш прогресс.",
    profile: "Здесь появятся настройки.",
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
 * it. v1 endpoints (auth, push) send English strings, which are shown only for a
 * conflict (409, e.g. "email already registered"); anything else gets the generic line.
 */
export function describeError(err: unknown, t: Dict): string {
  if (!(err instanceof ApiError)) return t.errors.offline;
  if (err.code) return errorText(err.code, t);
  if (err.status === 409 && err.message) return err.message;
  return t.errors.generic;
}
