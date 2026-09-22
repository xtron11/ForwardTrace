(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* шапка получает линию только после 24px скролла */
  var head = document.getElementById("siteHead");
  function onScroll() {
    head.classList.toggle("is-stuck", window.scrollY > 24);
  }
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  /* появление блоков */
  var revealables = document.querySelectorAll("[data-reveal]");
  if (reduced || !("IntersectionObserver" in window)) {
    for (var i = 0; i < revealables.length; i++) revealables[i].classList.add("is-in");
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry, index) {
        if (!entry.isIntersecting) return;
        var delay = index * 70;
        setTimeout(function () { entry.target.classList.add("is-in"); }, delay);
        io.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.15 });
    for (var j = 0; j < revealables.length; j++) io.observe(revealables[j]);
  }

  /* ─── «Знакомо?»: одна сцена на три проблемы ───
     Посетитель выбирает пункт — полотно меняет сцену. Сцена заводится,
     когда до неё действительно долистали, и не крутится впустую выше по странице. */
  (function recognizeScene() {
    var section = document.querySelector(".rec");
    if (!section) return;

    var items = [].slice.call(section.querySelectorAll(".rec-item"));
    var scenes = [].slice.call(section.querySelectorAll(".scn"));
    var counter = section.querySelector(".scn-count");
    if (!items.length || !scenes.length) return;

    var PAGES = 7;
    var countTimer = null;

    function byScene(n) {
      for (var i = 0; i < scenes.length; i++) {
        if (scenes[i].getAttribute("data-scene") === String(n)) return scenes[i];
      }
      return null;
    }

    /* Счётчик записей идёт вместе с падающими страницами: смысл сцены в том,
       что записей много, а картины из них не складывается. */
    function runCounter() {
      if (countTimer) { clearInterval(countTimer); countTimer = null; }
      if (!counter) return;
      if (reduced) { counter.textContent = String(PAGES); return; }
      var n = 0;
      counter.textContent = "0";
      countTimer = setInterval(function () {
        n += 1;
        counter.textContent = String(n);
        if (n >= PAGES) { clearInterval(countTimer); countTimer = null; }
      }, 190);
    }

    function show(n) {
      for (var i = 0; i < items.length; i++) {
        var on = items[i].getAttribute("data-scene") === String(n);
        items[i].classList.toggle("is-on", on);
        items[i].setAttribute("aria-pressed", on ? "true" : "false");
      }
      for (var j = 0; j < scenes.length; j++) {
        var live = scenes[j].getAttribute("data-scene") === String(n);
        scenes[j].classList.toggle("is-on", live);
        if (!live) scenes[j].classList.remove("is-live");
      }

      var scene = byScene(n);
      if (!scene) return;
      /* перезапуск css-анимаций: снять класс, заставить пересчитать стили, вернуть */
      scene.classList.remove("is-live");
      void scene.offsetWidth;
      scene.classList.add("is-live");

      if (n === 1) runCounter();
    }

    for (var i = 0; i < items.length; i++) {
      (function (item) {
        var n = Number(item.getAttribute("data-scene"));
        item.addEventListener("click", function () { show(n); });
        item.addEventListener("mouseenter", function () {
          if (window.matchMedia("(hover: hover)").matches) show(n);
        });
        item.addEventListener("focus", function () { show(n); });
      })(items[i]);
    }

    show(1);

  })();

  /* ─── «Две даты»: сближение двух записей ───
     Одна механика на все три варианта. В секцию пишется --p, прогресс её
     прохода через экран от 0 до 1, и класс .is-close, когда записи сошлись.
     Всё остальное — как именно они сходятся — решает css конкретного варианта.
     Диапазон намеренно короткий: около 60% высоты экрана, чтобы идея читалась
     за один экран, а не превращалась в длинный сторителлинг. */
  (function twoDates() {
    var sections = [].slice.call(document.querySelectorAll(".two"));
    if (!sections.length) return;

    var START = 0.86;   /* верх секции на этой доле высоты экрана — прогресс 0 */
    var RANGE = 0.60;   /* столько высоты экрана занимает всё сближение */
    var CLOSE = 0.92;   /* с этого прогресса записи считаются сошедшимися */

    var ticking = false;

    function visible(el) {
      return el.offsetParent !== null || el.getClientRects().length > 0;
    }

    function update() {
      ticking = false;
      var vh = window.innerHeight || document.documentElement.clientHeight;

      for (var i = 0; i < sections.length; i++) {
        var section = sections[i];
        if (!visible(section)) continue;

        var box = section.getBoundingClientRect();
        if (box.bottom < -vh || box.top > vh * 1.4) continue;

        var p = (vh * START - box.top) / (vh * RANGE);
        if (p < 0) p = 0;
        if (p > 1) p = 1;

        if (reduced) p = 1;

        section.style.setProperty("--p", p.toFixed(4));
        section.classList.toggle("is-close", p >= CLOSE);
      }
    }

    function request() {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(update);
    }

    update();
    window.addEventListener("scroll", request, { passive: true });
    window.addEventListener("resize", request, { passive: true });
    /* смена варианта меняет, какая секция на экране — пересчитываем сразу */
    document.addEventListener("ft:variant", function () { setTimeout(update, 0); });
  })();

  /* ─── продукт: три шага на одном аппарате ───
     Шаг выбирается рукой — экран телефона показывает этот шаг. Тот же способ
     управления, что и в «Знакомо?»: страница говорит с посетителем одним
     языком, а не набором разных трюков.
     Отдельно от выбора идёт --dp: положение аппарата в экране, от -1 до 1.
     Им живёт дыхание корпуса и ползущий по стеклу блик. */
  (function productDevice() {
    var section = document.querySelector(".product");
    if (!section) return;

    var steps = [].slice.call(section.querySelectorAll(".step"));
    var screens = [].slice.call(section.querySelectorAll(".app-scr"));
    var stage = section.querySelector(".device-stage");
    if (!steps.length || !screens.length) return;

    /* строки таймлайна проявляются по очереди — индекс нужен css */
    var rows = section.querySelectorAll(".tl-row");
    for (var r = 0; r < rows.length; r++) rows[r].style.setProperty("--i", r);

    /* датам в фоне нужен индекс, чтобы выстроиться по вертикали в нужном порядке */
    var chips = section.querySelectorAll(".pbg-dates i");
    for (var c = 0; c < chips.length; c++) {
      chips[c].style.setProperty("--i", c);
      chips[c].style.setProperty("--c", c % 3);
    }

    function show(n) {
      /* фон читает шаг и отвечает на него: на третьем разрозненное собирается */
      section.setAttribute("data-step", String(n));
      for (var i = 0; i < steps.length; i++) {
        var on = steps[i].getAttribute("data-step") === String(n);
        steps[i].classList.toggle("is-on", on);
        steps[i].setAttribute("aria-pressed", on ? "true" : "false");
      }
      for (var j = 0; j < screens.length; j++) {
        var live = screens[j].getAttribute("data-scr") === String(n);
        screens[j].classList.toggle("is-on", live);
        if (live) {
          /* перезапуск css-анимаций состояния */
          screens[j].classList.remove("is-on");
          void screens[j].offsetWidth;
          screens[j].classList.add("is-on");
        }
      }
    }

    for (var s = 0; s < steps.length; s++) {
      (function (step) {
        var n = Number(step.getAttribute("data-step"));
        step.addEventListener("click", function () { show(n); });
        step.addEventListener("mouseenter", function () {
          if (window.matchMedia("(hover: hover)").matches) show(n);
        });
        step.addEventListener("focus", function () { show(n); });
      })(steps[s]);
    }

    show(1);

    if (!stage || reduced) return;

    var ticking = false;

    function move() {
      ticking = false;
      var vh = window.innerHeight || document.documentElement.clientHeight;
      var box = stage.getBoundingClientRect();
      if (box.bottom < 0 || box.top > vh) return;
      /* -1 — аппарат только вошёл снизу, 0 — по центру экрана, 1 — уходит вверх */
      var mid = box.top + box.height / 2;
      var dp = (vh / 2 - mid) / (vh / 2 + box.height / 2);
      if (dp < -1) dp = -1;
      if (dp > 1) dp = 1;
      stage.style.setProperty("--dp", dp.toFixed(4));
    }

    function request() {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(move);
    }

    move();
    window.addEventListener("scroll", request, { passive: true });
    window.addEventListener("resize", request, { passive: true });
  })();

  /* ─── герой: видео, которое отматывается прокруткой ───
     Камера идёт от левого человека к его глазам, оттуда в дневник,
     дневник открывается и кадр гаснет — дальше начинается «Знакомо?».
     Видео включается только там, где оно уместно и реально готово:
     широкий экран, разрешённая анимация, загруженный файл. */
  (function heroScrollVideo() {
    var hero = document.querySelector(".hero");
    var stage = document.querySelector(".hero-stage");
    var video = document.querySelector(".hero-video");
    var copy = document.querySelector(".hero-copy");
    if (!hero || !stage || !video || reduced) return;

    var wide = window.matchMedia("(min-width: 901px)");
    if (!wide.matches) return;

    /* Файл не прописан в разметке и не грузится, пока мы не убедились,
       что видео здесь вообще будет: иначе телефоны качали бы мегабайты
       ради кадра, который у них всё равно статичный.
       1080p отдаём только тем, кому есть куда его показать. */
    var hd = video.getAttribute("data-src-hd");
    var sd = video.getAttribute("data-src-sd");
    video.src = (window.innerWidth >= 1600 && window.devicePixelRatio >= 1) ? (hd || sd) : (sd || hd);
    video.preload = "auto";
    video.load();

    var duration = 0;
    var target = 0;      /* куда просит прокрутка */
    var shown = 0;       /* где сейчас стоит кадр */
    var ticking = false;
    var armed = false;

    function progress() {
      var box = hero.getBoundingClientRect();
      var travel = hero.offsetHeight - stage.offsetHeight;
      if (travel <= 0) return 0;
      var p = -box.top / travel;
      return p < 0 ? 0 : p > 1 ? 1 : p;
    }

    function frame() {
      ticking = false;
      var p = progress();
      target = p * duration;

      /* догоняем цель плавно, иначе на тачпаде кадр дёргается */
      shown += (target - shown) * 0.18;
      if (Math.abs(target - shown) < 0.004) shown = target;

      if (video.readyState >= 2) {
        try { video.currentTime = shown; } catch (e) { /* ещё не ищется */ }
      }

      /* заголовок уходит, как только камера двинулась с места */
      if (copy) {
        var fade = p / 0.16;
        if (fade > 1) fade = 1;
        copy.style.opacity = String(1 - fade);
        copy.style.transform = "translate3d(0," + (-26 * fade).toFixed(2) + "px,0)";
        copy.style.pointerEvents = fade > 0.9 ? "none" : "";
      }

      if (Math.abs(target - shown) > 0.004) request();
    }

    function request() {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(frame);
    }

    /* Страница, открытая сразу с якорем (#recognize в новой вкладке), уже
       проложена браузером по короткому герою. Включение дорожки прокрутки
       добавляет к герою 220vh, всё нижнее уезжает вниз, и прежняя позиция
       оказывается в середине видео. Поэтому после включения возвращаемся
       к тому же якорю — но только если посетитель сам ещё не тронул страницу:
       рывок под руками хуже неверной позиции. */
    var touched = false;
    function touch() { touched = true; }
    window.addEventListener("wheel", touch, { passive: true });
    window.addEventListener("touchmove", touch, { passive: true });
    window.addEventListener("keydown", touch);
    document.addEventListener("click", touch);

    function realign() {
      if (touched) return;
      var id = window.location.hash.slice(1);
      if (!id) return;
      var anchor = document.getElementById(id);
      if (!anchor) return;
      /* мгновенно: плавная прокрутка здесь выглядела бы как самопроизвольный уезд */
      var root = document.documentElement;
      var smooth = root.style.scrollBehavior;
      root.style.scrollBehavior = "auto";
      anchor.scrollIntoView();
      root.style.scrollBehavior = smooth;
    }

    function arm() {
      if (armed) return;
      duration = video.duration;
      if (!duration || !isFinite(duration)) return;
      armed = true;
      video.pause();
      document.documentElement.classList.add("has-hero-video");
      video.classList.add("is-ready");
      realign();
      window.addEventListener("scroll", request, { passive: true });
      window.addEventListener("resize", request, { passive: true });
      request();
    }

    /* Safari отдаёт seek только после того, как отдал первый кадр */
    video.addEventListener("loadeddata", arm);
    video.addEventListener("canplay", arm);
    if (video.readyState >= 2) arm();

    /* если экран переехал в мобильную ширину — отдаём статичный кадр обратно */
    var onWide = function (e) {
      if (e.matches) return;
      document.documentElement.classList.remove("has-hero-video");
      video.classList.remove("is-ready");
      if (copy) { copy.style.opacity = ""; copy.style.transform = ""; copy.style.pointerEvents = ""; }
    };
    if (wide.addEventListener) wide.addEventListener("change", onWide);
  })();

  /* таблица на телефоне: строка становится блоком, колонка подписывает свою ячейку */
  function stackTable() {
    var table = document.querySelector(".ctable");
    if (!table) return;
    var heads = table.querySelectorAll("thead th");
    if (heads.length < 3) return;
    var rows = table.querySelectorAll("tbody tr");
    for (var r = 0; r < rows.length; r++) {
      var cells = rows[r].querySelectorAll("td");
      for (var c = 0; c < cells.length; c++) {
        cells[c].setAttribute("data-col", heads[c + 1].textContent);
      }
    }
  }
  stackTable();
  document.addEventListener("ft:lang", stackTable);
})();
