/* ЛЕСА ДЛЯ ВЫБОРА, НЕ ЧАСТЬ ДИЗАЙНА.
   Варианты фона секции «продукт»:
     A · поле дат   — разрозненные даты, на третьем шаге сходятся в линию
     B · реестр дней — сетка суток, часть записана
     C · свет и нить — направленный свет и одна вертикаль

   Когда вариант выбран, удаляется целиком: этот файл, строка <script>
   в index.html, лишние слои из .pbg в разметке и их правила в style.css.

   Ссылкой: ?bg=a|b|c   Клавиша: B */
(function () {
  "use strict";

  var GROUPS = [
    { key: "bg", attr: "data-bg", store: "ft_bg", label: "Фон",
      opts: [["a", "A · даты"], ["b", "B · реестр"], ["c", "C · свет"]], hot: ["b", "и"], evt: null }
  ];

  function stored(key, v) {
    try {
      if (v === undefined) return window.localStorage.getItem(key);
      window.localStorage.setItem(key, v);
    } catch (e) { /* file:// или закрытое хранилище */ }
    return null;
  }

  for (var g = 0; g < GROUPS.length; g++) {
    var grp = GROUPS[g];
    var allowed = grp.opts.map(function (o) { return o[0]; });
    var m = new RegExp("[?&]" + grp.key + "=([a-z]+)", "i").exec(window.location.search);
    var q = m && m[1].toLowerCase();
    grp.value = (allowed.indexOf(q) !== -1 && q) || stored(grp.store) || allowed[0];
    if (allowed.indexOf(grp.value) === -1) grp.value = allowed[0];
    document.documentElement.setAttribute(grp.attr, grp.value);
  }

  var bar;

  function sync() {
    if (!bar) return;
    for (var g = 0; g < GROUPS.length; g++) {
      var b = bar.querySelectorAll("[data-g='" + GROUPS[g].key + "']");
      for (var i = 0; i < b.length; i++) {
        b[i].setAttribute("aria-pressed", b[i].getAttribute("data-v") === GROUPS[g].value ? "true" : "false");
      }
    }
  }

  function apply(grp, next) {
    grp.value = next;
    document.documentElement.setAttribute(grp.attr, next);
    stored(grp.store, next);
    sync();
    if (grp.evt) document.dispatchEvent(new CustomEvent(grp.evt, { detail: { mode: next } }));
  }

  function build() {
    var css = [
      ".ft-bg{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:80;",
      "display:grid;gap:6px;padding:10px 12px;border-radius:18px;",
      "border:1px solid #32405F;background:rgba(10,16,34,.88);backdrop-filter:blur(12px);",
      "-webkit-backdrop-filter:blur(12px);font:500 12px/1 'JetBrains Mono',ui-monospace,monospace;color:#A5B2C9}",
      ".ft-bg__row{display:flex;align-items:center;gap:8px}",
      ".ft-bg__tag{letter-spacing:.14em;text-transform:uppercase;color:#8090A8;padding-left:6px;min-width:66px}",
      ".ft-bg button{appearance:none;border:1px solid transparent;background:none;color:#A5B2C9;",
      "font:inherit;padding:7px 13px;border-radius:999px;cursor:pointer}",
      ".ft-bg button:hover{color:#E9EEF8}",
      ".ft-bg button[aria-pressed='true']{background:#8FB4FF;border-color:#8FB4FF;color:#0A1022}",
      ".ft-bg__hide{position:absolute;top:5px;right:8px;color:#8090A8;padding:3px 6px !important}",
      ".ft-bg.is-hidden{display:none}"
    ].join("");
    var tag = document.createElement("style");
    tag.textContent = css;
    document.head.appendChild(tag);

    bar = document.createElement("div");
    bar.className = "ft-bg";
    bar.setAttribute("role", "region");
    bar.setAttribute("aria-label", "Варианты секций");
    var html = "";
    for (var g = 0; g < GROUPS.length; g++) {
      html += '<div class="ft-bg__row"><span class="ft-bg__tag">' + GROUPS[g].label + "</span>";
      for (var i = 0; i < GROUPS[g].opts.length; i++) {
        html += '<button type="button" data-g="' + GROUPS[g].key +
                '" data-v="' + GROUPS[g].opts[i][0] + '">' + GROUPS[g].opts[i][1] + "</button>";
      }
      html += "</div>";
    }
    html += '<button type="button" class="ft-bg__hide" aria-label="Скрыть панель">&times;</button>';
    bar.innerHTML = html;

    var btns = bar.querySelectorAll("[data-v]");
    for (var k = 0; k < btns.length; k++) {
      btns[k].addEventListener("click", function (e) {
        var key = e.currentTarget.getAttribute("data-g");
        for (var n = 0; n < GROUPS.length; n++) {
          if (GROUPS[n].key !== key) continue;
          apply(GROUPS[n], e.currentTarget.getAttribute("data-v"));
          var target = document.querySelector(key === "cmp" ? ".compare" : ".product");
          if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      });
    }
    bar.querySelector(".ft-bg__hide").addEventListener("click", function () {
      bar.classList.add("is-hidden");
    });

    document.body.appendChild(bar);
    sync();
  }

  document.addEventListener("keydown", function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var t = (e.target && e.target.tagName) || "";
    if (t === "INPUT" || t === "TEXTAREA") return;
    var k = (e.key || "").toLowerCase();
    for (var g = 0; g < GROUPS.length; g++) {
      if (GROUPS[g].hot.indexOf(k) === -1) continue;
      var at = 0;
      for (var i = 0; i < GROUPS[g].opts.length; i++) if (GROUPS[g].opts[i][0] === GROUPS[g].value) at = i;
      apply(GROUPS[g], GROUPS[g].opts[(at + 1) % GROUPS[g].opts.length][0]);
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
})();
