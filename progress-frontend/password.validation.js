const passwordInput = document.getElementById("password");
const loginInput = document.getElementById("login");
const emailInput = document.getElementById("email");
const nameInput = document.getElementById("name");

const criteria = {
  length: document.getElementById("length"),
  maxBytes: document.getElementById("max-bytes"),
  lowercase: document.getElementById("lowercase"),
  uppercase: document.getElementById("uppercase"),
  number: document.getElementById("number"),
  symbol: document.getElementById("symbol"),
  personal: document.getElementById("personal"),
};

const criterionLabels = new Map(
  Object.values(criteria).map((el) => [el, el.textContent]),
);

function normalize(value) {
  return value
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]/gu, "");
}

function getPersonalTerms() {
  const emailLocalPart = emailInput.value.split("@", 1)[0];
  const words = (s) => s.match(/[\p{L}\p{N}]+/gu) ?? [];
  return [
    loginInput.value,
    ...words(loginInput.value),
    emailInput.value,
    emailLocalPart,
    ...words(nameInput.value),
  ]
    .map(normalize)
    .filter((term) => term.length > 2);
}

function setCriterion(element, passed) {
  element.classList.toggle("valid", passed);
  element.textContent = `${passed ? "✓" : "✗"} ${criterionLabels.get(element)}`;
}

function checkPassword() {
  const password = passwordInput.value;
  const normalizedPassword = normalize(password);
  const personalTerms = getPersonalTerms();

  criteria.personal.hidden = personalTerms.length === 0;

  const valid = {
    length: [...password].length >= 10,
    maxBytes: new TextEncoder().encode(password).length <= 72,
    lowercase: /\p{Ll}/u.test(password),
    uppercase: /\p{Lu}/u.test(password),
    number: /\p{Nd}/u.test(password),
    symbol: /[\p{P}\p{S}]/u.test(password),
    personal: !personalTerms.some((t) => normalizedPassword.includes(t)),
  };

  for (const [key, element] of Object.entries(criteria)) {
    setCriterion(element, valid[key]);
  }
}

for (const input of [passwordInput, loginInput, emailInput, nameInput]) {
  input.addEventListener("input", checkPassword);
}

checkPassword();
