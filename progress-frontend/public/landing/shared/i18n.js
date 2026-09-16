/* Язык страницы: определяется по браузеру, без переключателя — как в приложении.
   Это рабочий код лендинга, а не леса: переключатель вариантов живёт отдельно. */
(function () {
  "use strict";

  function store(key, value) {
    try {
      if (value === undefined) return window.localStorage.getItem(key);
      window.localStorage.setItem(key, value);
    } catch (e) { /* file:// или закрытое хранилище */ }
    return null;
  }

  function query(name) {
    var m = new RegExp("[?&]" + name + "=([^&#]*)").exec(window.location.search);
    return m ? decodeURIComponent(m[1]) : null;
  }

  function pick() {
    var q = query("lang");
    if (q === "ru" || q === "en") return q;
    var saved = store("ft_lang");
    if (saved === "ru" || saved === "en") return saved;
    return /^ru\b/i.test(navigator.language || "") ? "ru" : "en";
  }

  var lang = pick();

  function t(key) {
    var dict = (window.FT_COPY && window.FT_COPY[lang]) || (window.FT_COPY && window.FT_COPY.ru) || {};
    return Object.prototype.hasOwnProperty.call(dict, key) ? dict[key] : key;
  }

  function apply() {
    document.documentElement.lang = lang;
    var nodes = document.querySelectorAll("[data-t]");
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].textContent = t(nodes[i].getAttribute("data-t"));
    }
    /* строки с разметкой: выделения внутри цитат живут в самом переводе,
       поэтому их нельзя ставить через textContent. Значения приходят из
       shared/copy.js, пользовательского ввода здесь нет. */
    var rich = document.querySelectorAll("[data-t-html]");
    for (var r = 0; r < rich.length; r++) {
      rich[r].innerHTML = t(rich[r].getAttribute("data-t-html"));
    }

    var labelled = document.querySelectorAll("[data-t-label]");
    for (var j = 0; j < labelled.length; j++) {
      labelled[j].setAttribute("aria-label", t(labelled[j].getAttribute("data-t-label")));
    }
    if (document.querySelector("[data-t='meta.title']") || t("meta.title") !== "meta.title") {
      document.title = t("meta.title");
    }
    var desc = document.querySelector('meta[name="description"]');
    if (desc) desc.setAttribute("content", t("meta.desc"));
    document.dispatchEvent(new CustomEvent("ft:lang", { detail: { lang: lang } }));
  }

  function setLang(next) {
    if (next !== "ru" && next !== "en") return;
    if (next === lang) return;
    lang = next;
    store("ft_lang", next);
    apply();
  }

  window.FT = {
    t: t,
    apply: apply,
    setLang: setLang,
    lang: function () { return lang; }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply);
  } else {
    apply();
  }
})();
