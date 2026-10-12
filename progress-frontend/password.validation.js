const passwordInput = document.getElementById("password");
const loginInput = document.getElementById("login");
const emailInput = document.getElementById("email");
const nameInput = document.getElementById("name");
const scoreOutput = document.getElementById("score");
const resultOutput = document.getElementById("result");

const criteria = Object.fromEntries(Object.entries({
  length: document.getElementById("length"),
  maxBytes: document.getElementById("max-bytes"),
  lowercase: document.getElementById("lowercase"),
  uppercase: document.getElementById("uppercase"),
  number: document.getElementById("number"),
  symbol: document.getElementById("symbol"),
  common: document.getElementById("common"),
  personal: document.getElementById("personal"),
}).filter(([, element]) => element));

const scoreCriteria = Object.fromEntries(Object.entries({
  length: document.getElementById("score-length"),
  long: document.getElementById("score-long"),
  case: document.getElementById("score-case"),
  number: document.getElementById("score-number"),
  symbol: document.getElementById("score-symbol"),
}).filter(([, element]) => element));

const criterionLabels = new Map(
  [...Object.values(criteria), ...Object.values(scoreCriteria)].map((element) => [
    element,
    element.textContent,
  ]),
);

const commonPasswords = new Set([
  "123456",
  "12345678",
  "123456789",
  "1234567890",
  "1234567",
  "111111",
  "000000",
  "abc123",
  "123qwe",
  "1q2w3e4r",
  "qwerty",
  "qwerty123",
  "qwertyuiop",
  "пароль",
  "пароль123",
  "password",
  "password1",
  "password123",
  "passw0rd",
  "admin",
  "admin123",
  "letmein",
  "welcome",
  "welcome1",
  "iloveyou",
  "sunshine",
  "master",
  "football",
  "secret",
  "changeme",
  "dragon",
  "monkey",
]);

function normalize(value) {
  return value
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]/gu, "");
}

function getPersonalTerms() {
  const emailLocalPart = emailInput.value.split("@", 1)[0];
  const nameWords = nameInput.value.match(/[\p{L}\p{N}]+/gu) ?? [];
  return [
    loginInput.value,
    ...(loginInput.value.match(/[\p{L}\p{N}]+/gu) ?? []),
    emailInput.value,
    emailLocalPart,
    ...nameWords,
  ]
    .map(normalize)
    .filter((term) => term.length > 1);
}

function containsPersonalInfo(password, personalTerms) {
  const normalizedPassword = normalize(password);
  return personalTerms.some((term) => normalizedPassword.includes(term));
}

function setCriterion(element, passed) {
  element.classList.toggle("valid", passed);
  element.textContent = `${passed ? "✓" : "✗"} ${criterionLabels.get(element)}`;
}

function checkPassword() {
  const password = passwordInput.value;
  const characterCount = [...password].length;
  const byteCount = new TextEncoder().encode(password).length;
  const hasLowercase = /\p{Ll}/u.test(password);
  const hasUppercase = /\p{Lu}/u.test(password);
  const hasNumber = /\p{N}/u.test(password);
  const hasSymbol = /[\p{P}\p{S}]/u.test(password);
  const isCommon = commonPasswords.has(normalize(password));
  const personalTerms = getPersonalTerms();
  const hasPersonalInfo = containsPersonalInfo(password, personalTerms);

  if (criteria.personal) {
    criteria.personal.hidden = personalTerms.length === 0;
  }

  const valid = {
    length: characterCount >= 10,
    maxBytes: byteCount <= 72,
    lowercase: hasLowercase,
    uppercase: hasUppercase,
    number: hasNumber,
    symbol: hasSymbol,
    common: !isCommon,
    personal: !hasPersonalInfo,
  };

  for (const [key, element] of Object.entries(criteria)) {
    setCriterion(element, valid[key]);
  }

  const points = {
    length: characterCount >= 10,
    long: characterCount >= 14,
    case: hasLowercase && hasUppercase,
    number: hasNumber,
    symbol: hasSymbol,
  };
  const score = Object.values(points).filter(Boolean).length;
  const rating =
    score <= 2 ? "слабо" : score === 3 ? "нормально" : score === 4 ? "хорошо" : "надёжный";

  for (const [key, element] of Object.entries(scoreCriteria)) {
    setCriterion(element, points[key]);
  }
  scoreOutput.textContent = `Надёжность: ${score}/5 — ${rating}`;

  const isValid = Object.values(valid).every(Boolean);
  resultOutput.textContent = isValid ? "Пароль соответствует всем требованиям." : "";
}

for (const input of [passwordInput, loginInput, emailInput, nameInput]) {
  input.addEventListener("input", checkPassword);
}

checkPassword();
