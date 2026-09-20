<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import PWAInstallButton from '../components/PWAInstallButton.vue';
import AudioRecordingModal from '../components/AudioRecordingModal.vue';
import { useTheme } from '../composables/useTheme';
import { useTimelineStore } from '../composables/useTimelineStore';

const router = useRouter();
const { isDark, toggleDark } = useTheme();
const { totalDays } = useTimelineStore();

const isRecordModalOpen = ref(false);
const activeScene = ref<1 | 2 | 3>(1);

const openRecordingModal = () => {
  isRecordModalOpen.value = true;
};

const closeRecordingModal = () => {
  isRecordModalOpen.value = false;
};

const onAudioRecorded = () => {
  // after recording, optional navigate to today or stay
};

const navigateToApp = () => {
  router.push('/today');
};
</script>

<template>
  <div class="min-h-screen bg-bg-primary text-text-primary selection:bg-accent selection:text-bg-primary antialiased font-sans">
    
    <!-- Real Audio Recording Modal with animated visualizer -->
    <AudioRecordingModal
      :is-open="isRecordModalOpen"
      @close="closeRecordingModal"
      @recorded="onAudioRecorded"
    />

    <!-- Header / Navigation Bar -->
    <header class="sticky top-0 z-40 w-full border-b border-border-color bg-bg-primary/80 backdrop-blur-md transition-colors">
      <div class="max-w-[1240px] mx-auto px-6 h-16 flex items-center justify-between">
        
        <!-- Logo -->
        <a href="#top" class="flex items-center gap-2.5 text-text-primary hover:text-accent transition-colors">
          <svg width="20" height="20" viewBox="0 0 18 18" aria-hidden="true" focusable="false" class="text-accent">
            <path d="M2 13.5 C5.5 13.5 5.5 4.5 9 4.5 C12.5 4.5 12.5 9 16 9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <circle cx="16" cy="9" r="2.2" fill="currentColor"/>
          </svg>
          <span class="font-display font-semibold text-[17px] tracking-tight">ForwardTrace</span>
        </a>

        <!-- Navigation Links -->
        <nav class="hidden md:flex items-center gap-8 font-sans text-[14px] text-text-secondary">
          <a href="#recognize" class="hover:text-text-primary transition-colors">Знакомо</a>
          <a href="#moments" class="hover:text-text-primary transition-colors">Два момента</a>
          <a href="#compare" class="hover:text-text-primary transition-colors">Сравнение</a>
          <router-link to="/today" class="hover:text-text-primary transition-colors">Кабинет</router-link>
        </nav>

        <!-- Right Actions -->
        <div class="flex items-center gap-3">
          <!-- Theme Toggle -->
          <button
            @click="toggleDark"
            class="p-2 rounded-xl text-text-muted hover:text-text-primary hover:bg-card-bg transition-colors"
            title="Переключить тему"
            aria-label="Переключить тему"
          >
            <svg v-if="!isDark" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="5"></circle>
              <line x1="12" y1="1" x2="12" y2="3"></line>
              <line x1="12" y1="21" x2="12" y2="23"></line>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
              <line x1="1" y1="12" x2="3" y2="12"></line>
              <line x1="21" y1="12" x2="23" y2="12"></line>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
            </svg>
          </button>

          <!-- PWA Button -->
          <div class="hidden sm:block">
            <PWAInstallButton />
          </div>

          <!-- Direct Voice Record Trigger -->
          <button
            @click="openRecordingModal"
            class="flex items-center gap-2 px-3.5 py-1.5 rounded-xl border border-accent/40 bg-accent-light text-accent text-[13px] font-mono font-medium hover:bg-accent hover:text-[#0A1022] transition-all"
            title="Записать голос прямо сейчас"
          >
            <span class="w-2 h-2 rounded-full bg-accent animate-ping"></span>
            Записать
          </button>

          <!-- Navigation to app -->
          <button
            @click="navigateToApp"
            class="hidden sm:inline-flex px-4 py-1.5 rounded-xl bg-accent text-[#0A1022] text-[13px] font-medium font-sans hover:bg-accent-hover hover:text-[#FFFFFF] transition-all"
          >
            Войти
          </button>
        </div>
      </div>
    </header>

    <!-- HERO SECTION -->
    <section id="top" class="relative pt-16 pb-24 md:pt-24 md:pb-36 overflow-hidden">
      <!-- Ambient decorative glow -->
      <div class="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-accent/10 rounded-full blur-[140px] pointer-events-none"></div>

      <div class="max-w-[1200px] mx-auto px-6 relative z-10">
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
          
          <!-- Left Column: Copy & Actions -->
          <div class="lg:col-span-7">
            <!-- Monospace Label -->
            <div class="inline-flex items-center gap-2 font-mono text-[11px] tracking-widest uppercase text-accent mb-6 px-3 py-1 rounded-full bg-card-surface border border-border-color">
              <span class="w-1.5 h-1.5 rounded-full bg-accent"></span>
              Хроника пути · ForwardTrace
            </div>

            <h1 class="font-display font-semibold text-[clamp(2rem,4.5vw,3.6rem)] leading-[1.12] tracking-[-0.035em] text-text-primary mb-6">
              Вы изменились.<br/>
              <em class="italic text-accent font-normal">Просто вы этого не замечаете.</em>
            </h1>

            <p class="font-sans text-[18px] md:text-[20px] leading-relaxed text-text-secondary max-w-[540px] mb-10">
              Вы работаете неделями и кажется, будто ничего не сдвинулось. Говорите 30 секунд в день — и перечитывайте факты своего движения собственными словами.
            </p>

            <!-- Action Buttons with Record Trigger -->
            <div class="flex flex-wrap items-center gap-4">
              <!-- Big Recording Trigger with Pulsing Animation -->
              <button
                @click="openRecordingModal"
                class="group relative flex items-center gap-3 px-7 py-4 rounded-2xl bg-accent text-[#0A1022] font-sans font-semibold text-[15px] shadow-xl shadow-accent/20 hover:bg-accent-hover hover:text-[#FFFFFF] transition-all active:scale-95"
              >
                <!-- Animated Micro Wave Indicator -->
                <span class="relative flex h-3 w-3">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#0A1022] opacity-60"></span>
                  <span class="relative inline-flex rounded-full h-3 w-3 bg-[#0A1022] group-hover:bg-[#FFFFFF]"></span>
                </span>
                <span>Начать запись (30 сек)</span>
                <svg class="w-4 h-4 transition-transform group-hover:translate-x-1" viewBox="0 0 16 10" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M0 5h14M10 1l4 4-4 4"/>
                </svg>
              </button>

              <!-- Link to Today Dashboard -->
              <router-link
                to="/today"
                class="px-6 py-4 rounded-2xl border border-border-strong bg-card-bg/60 hover:bg-card-bg text-text-primary font-sans font-medium text-[15px] hover:border-accent transition-all"
              >
                В кабинет ({{ totalDays }} дней)
              </router-link>
            </div>

            <!-- Hint text -->
            <p class="mt-5 font-mono text-[11px] tracking-wider text-text-muted">
              Первая запись занимает тридцать секунд · микрофон без установки
            </p>
          </div>

          <!-- Right Column: Interactive Phone Mockup Card -->
          <div class="lg:col-span-5">
            <div class="relative mx-auto max-w-[380px] bg-card-bg border border-border-color rounded-[32px] p-6 sm:p-7 shadow-2xl shadow-black/40">
              
              <!-- Top notch / status -->
              <div class="flex items-center justify-between font-mono text-[11px] text-text-muted pb-4 border-b border-border-color">
                <span class="uppercase tracking-wider">Сегодня · 3 сентября</span>
                <span class="px-2 py-0.5 rounded bg-card-surface text-accent font-medium text-[10px]">Расшифровано</span>
              </div>

              <!-- Spoken text block -->
              <div class="my-6">
                <p class="font-mono text-[10px] tracking-widest uppercase text-text-muted mb-2">Сказано</p>
                <p class="font-sans text-[15px] text-text-primary leading-relaxed bg-card-surface/70 p-3.5 rounded-xl border border-border-color">
                  «…всё равно закончил работу над прототипом и впервые показал его людям.»
                </p>
              </div>

              <!-- Extracted fact -->
              <div class="mb-6 border-l-2 border-accent pl-3">
                <p class="font-mono text-[10px] tracking-widest uppercase text-text-muted mb-1">Извлечено</p>
                <p class="font-serif italic text-[14px] text-text-secondary leading-snug">
                  показал прототип людям — первый отклик со стороны
                </p>
              </div>

              <!-- Streak & Goal context -->
              <div class="bg-card-surface/50 rounded-xl p-3.5 border border-border-color mb-6">
                <div class="flex justify-between items-center text-xs font-mono text-text-muted mb-2">
                  <span>Цель · довести прототип</span>
                  <span class="text-accent font-medium">4 из 7 дней</span>
                </div>
                <div class="w-full h-1.5 bg-border-color rounded-full overflow-hidden">
                  <div class="w-[57%] h-full bg-accent rounded-full"></div>
                </div>
              </div>

              <!-- Interactive In-card Voice Button -->
              <button
                @click="openRecordingModal"
                class="w-full py-3 rounded-xl bg-accent text-[#0A1022] font-mono text-[12px] uppercase tracking-wider font-bold hover:bg-accent-hover hover:text-[#FFFFFF] transition-all flex items-center justify-center gap-2 active:scale-98 shadow-md"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                  <line x1="12" y1="19" x2="12" y2="22"></line>
                </svg>
                Рассказать день
              </button>

              <!-- Timeline mini trail -->
              <div class="mt-6 pt-4 border-t border-border-color flex justify-between text-[11px] font-mono text-text-muted">
                <span>3 сен</span>
                <span>17 авг</span>
                <span>2 июл</span>
                <span>14 фев</span>
              </div>
            </div>
          </div>

        </div>
      </div>
    </section>

    <!-- SECTION 1: «ЗНАКОМО?» (Interactive Problem Picker) -->
    <section id="recognize" class="py-20 md:py-32 border-t border-border-color bg-card-bg/30">
      <div class="max-w-[1200px] mx-auto px-6">
        
        <div class="mb-12">
          <h2 class="font-display font-semibold text-[26px] md:text-[34px] tracking-tight text-text-primary mb-3">
            Знакомо?
          </h2>
          <p class="font-mono text-xs tracking-widest uppercase text-text-muted">
            Выберите проблему, чтобы увидеть её
          </p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          <!-- Problem buttons column -->
          <div class="lg:col-span-6 space-y-4">
            
            <!-- Item 01 -->
            <button
              @click="activeScene = 1"
              type="button"
              class="w-full text-left p-6 rounded-2xl border transition-all"
              :class="activeScene === 1 ? 'border-accent bg-card-surface shadow-lg' : 'border-border-color bg-card-bg hover:border-border-strong'"
            >
              <div class="flex items-baseline gap-4 mb-2">
                <span class="font-mono font-bold text-sm" :class="activeScene === 1 ? 'text-accent' : 'text-text-muted'">01</span>
                <h3 class="font-sans font-medium text-[17px] text-text-primary">
                  Я вёл дневник, но так и не увидел своих изменений.
                </h3>
              </div>
              <p class="font-sans text-sm text-text-secondary pl-8 leading-relaxed">
                Я записывал мысли неделями и месяцами. А когда перечитывал, видел просто набор отдельных записей.
              </p>
            </button>

            <!-- Item 02 -->
            <button
              @click="activeScene = 2"
              type="button"
              class="w-full text-left p-6 rounded-2xl border transition-all"
              :class="activeScene === 2 ? 'border-accent bg-card-surface shadow-lg' : 'border-border-color bg-card-bg hover:border-border-strong'"
            >
              <div class="flex items-baseline gap-4 mb-2">
                <span class="font-mono font-bold text-sm" :class="activeScene === 2 ? 'text-accent' : 'text-text-muted'">02</span>
                <h3 class="font-sans font-medium text-[17px] text-text-primary">
                  Я всё время начинаю заново.
                </h3>
              </div>
              <p class="font-sans text-sm text-text-secondary pl-8 leading-relaxed">
                Ставлю цели, какое-то время держусь, потом теряю темп. А через месяц уже не помню, зачем вообще начинал.
              </p>
            </button>

            <!-- Item 03 -->
            <button
              @click="activeScene = 3"
              type="button"
              class="w-full text-left p-6 rounded-2xl border transition-all"
              :class="activeScene === 3 ? 'border-accent bg-card-surface shadow-lg' : 'border-border-color bg-card-bg hover:border-border-strong'"
            >
              <div class="flex items-baseline gap-4 mb-2">
                <span class="font-mono font-bold text-sm" :class="activeScene === 3 ? 'text-accent' : 'text-text-muted'">03</span>
                <h3 class="font-sans font-medium text-[17px] text-text-primary">
                  Я отмечал всё подряд — и всё равно не понял, что изменилось.
                </h3>
              </div>
              <p class="font-sans text-sm text-text-secondary pl-8 leading-relaxed">
                У меня есть привычки, серии и статистика. Но цифры и галочки не показывают, как изменились мои мысли и поведение.
              </p>
            </button>

          </div>

          <!-- Problem Visualizer Stage -->
          <div class="lg:col-span-6">
            <div class="bg-card-bg border border-border-color rounded-3xl p-8 min-h-[360px] flex flex-col justify-between">
              
              <!-- Scene 1: Scattered Pages -->
              <div v-if="activeScene === 1" class="space-y-4">
                <div class="flex justify-between font-mono text-xs text-text-muted mb-4">
                  <span>Стопка записей</span>
                  <span class="text-accent font-bold">7 записей без связи</span>
                </div>
                <div class="grid grid-cols-3 sm:grid-cols-4 gap-3">
                  <div v-for="d in ['12.11', '27.11', '03.01', '19.01', '14.02', '02.03', '27.04']" :key="d" class="p-3 bg-card-surface border border-border-color rounded-xl text-center">
                    <span class="font-mono text-xs text-accent font-semibold">{{ d }}</span>
                    <div class="w-full h-1 bg-border-color mt-2 rounded"></div>
                    <div class="w-3/4 h-1 bg-border-color mt-1 rounded"></div>
                  </div>
                </div>
                <p class="font-serif italic text-base text-text-secondary mt-8 pt-6 border-t border-border-color">
                  «Записи копятся. Но общей картины и понимания динамики из них не складывается.»
                </p>
              </div>

              <!-- Scene 2: The Loop -->
              <div v-else-if="activeScene === 2" class="space-y-6">
                <div class="flex justify-between font-mono text-xs text-text-muted">
                  <span>Замкнутый цикл</span>
                  <span class="text-amber-400 font-bold">Повторение</span>
                </div>
                <div class="grid grid-cols-2 gap-4 text-center">
                  <div class="p-4 bg-card-surface border border-border-color rounded-xl">
                    <div class="font-mono text-xs text-accent uppercase tracking-wider mb-1">01 Цель</div>
                    <p class="text-xs text-text-secondary">Ставлю высокую планку</p>
                  </div>
                  <div class="p-4 bg-card-surface border border-border-color rounded-xl">
                    <div class="font-mono text-xs text-emerald-400 uppercase tracking-wider mb-1">02 Прогресс</div>
                    <p class="text-xs text-text-secondary">Держусь 2 недели</p>
                  </div>
                  <div class="p-4 bg-card-surface border border-border-color rounded-xl">
                    <div class="font-mono text-xs text-amber-400 uppercase tracking-wider mb-1">03 Спад</div>
                    <p class="text-xs text-text-secondary">Теряю темп и ритм</p>
                  </div>
                  <div class="p-4 bg-card-surface border border-border-color rounded-xl">
                    <div class="font-mono text-xs text-[#FF5C5C] uppercase tracking-wider mb-1">04 Заново</div>
                    <p class="text-xs text-text-secondary">Забыл, зачем начинал</p>
                  </div>
                </div>
                <p class="font-serif italic text-base text-text-secondary pt-4 border-t border-border-color">
                  «Круг замыкается и начинается снова, если не фиксировать внутренние сдвиги.»
                </p>
              </div>

              <!-- Scene 3: Checkboxes vs Meaning -->
              <div v-else-if="activeScene === 3" class="space-y-6">
                <div class="flex justify-between font-mono text-xs text-text-muted">
                  <span>Сухая статистика</span>
                  <span class="text-text-muted font-bold">Галочки</span>
                </div>
                <div class="flex items-center gap-6 p-4 bg-card-surface rounded-2xl border border-border-color">
                  <div class="text-4xl font-display font-bold text-accent">24</div>
                  <div class="font-mono text-xs text-text-secondary">
                    дня подряд выполнено<br/>
                    <span class="text-text-muted">но состояние не изменилось</span>
                  </div>
                </div>
                <p class="font-serif italic text-base text-text-secondary pt-4 border-t border-border-color">
                  «Цифры и галочки не показывают, как на самом деле изменились ваши мысли и отношение к трудностям.»
                </p>
              </div>

              <!-- Bottom Action -->
              <div class="pt-6 border-t border-border-color flex justify-end">
                <button
                  @click="openRecordingModal"
                  class="font-mono text-xs uppercase tracking-wider text-accent hover:text-accent-hover font-semibold flex items-center gap-2"
                >
                  Решить это записью
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </button>
              </div>

            </div>
          </div>

        </div>

      </div>
    </section>

    <!-- SECTION 2: «ДВЕ ДАТЫ. ВАШИ СОБСТВЕННЫЕ СЛОВА» -->
    <section id="moments" class="py-20 md:py-32 border-t border-border-color relative">
      <div class="max-w-[1200px] mx-auto px-6">
        
        <div class="max-w-[700px] mb-16">
          <h2 class="font-display font-semibold text-[26px] md:text-[36px] tracking-tight text-text-primary mb-4">
            Две даты. <em class="italic text-accent font-normal">Ваши собственные слова.</em>
          </h2>
          <p class="font-mono text-xs tracking-widest uppercase text-accent">
            14 дней между записями
          </p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-8 relative">
          
          <!-- Card 1: 14 февраля -->
          <article class="p-8 rounded-3xl bg-card-bg border border-border-color relative">
            <span class="font-mono text-xs tracking-widest uppercase text-text-muted block mb-4">14 февраля</span>
            <blockquote class="font-sans text-[17px] text-text-primary leading-relaxed">
              Я вообще не понимаю, что мне делать дальше.
              <span class="text-accent font-medium underline decoration-accent/40 decoration-2 underline-offset-4">
                Сил ни на что нет.
              </span>
              Уже несколько дней просто
              <span class="text-accent font-medium underline decoration-accent/40 decoration-2 underline-offset-4">
                откладываю всё на потом
              </span>.
            </blockquote>
          </article>

          <!-- Card 2: 28 февраля -->
          <article class="p-8 rounded-3xl bg-card-bg border border-accent/40 shadow-xl shadow-accent/5 relative">
            <span class="font-mono text-xs tracking-widest uppercase text-accent block mb-4">28 февраля</span>
            <blockquote class="font-sans text-[17px] text-text-primary leading-relaxed">
              Сегодня я
              <span class="text-accent font-medium underline decoration-accent/40 decoration-2 underline-offset-4">
                снова был без сил
              </span>.
              Хотел вообще ничего не делать. Но
              <span class="text-accent font-medium underline decoration-accent/40 decoration-2 underline-offset-4">
                всё-таки сел и позанимался английским
              </span>.
              Честно говоря, мне всё ещё кажется, что это слишком мало.
            </blockquote>
          </article>

        </div>

        <!-- What ForwardTrace Noticed -->
        <div class="mt-8 p-8 rounded-3xl bg-card-surface border border-border-color">
          <p class="font-mono text-[11px] tracking-widest uppercase text-accent mb-3">
            Что заметил ForwardTrace
          </p>
          <p class="font-serif italic text-[18px] md:text-[20px] text-text-primary leading-relaxed max-w-[850px]">
            «Две недели назад вы писали, что не знаете, что делать дальше, и что сил ни на что нет. Сегодня сил снова не было — но вы всё равно сели и позанимались.»
          </p>
          <div class="mt-6 pt-6 border-t border-border-color flex flex-col sm:flex-row justify-between sm:items-center gap-4 text-xs font-mono text-text-muted">
            <span>Мы не говорим, что вы изменились. Мы показываем то, чего вы могли не заметить.</span>
            <span class="text-[10px]">Демонстрационный пример из системы</span>
          </div>
        </div>

      </div>
    </section>

    <!-- SECTION 3: СРАВНЕНИЕ («РЯДОМ С ТЕМ, ЧЕМ ВЫ УЖЕ ПОЛЬЗУЕТЕСЬ») -->
    <section id="compare" class="py-20 md:py-32 border-t border-border-color bg-card-bg/30">
      <div class="max-w-[1200px] mx-auto px-6">
        
        <div class="max-w-[700px] mb-16">
          <h2 class="font-display font-semibold text-[26px] md:text-[36px] tracking-tight text-text-primary mb-4">
            Рядом с тем, чем вы уже пользуетесь
          </h2>
          <p class="font-sans text-[17px] text-text-secondary leading-relaxed">
            Каждый из этих инструментов делает свою работу. Ни один из них не устроен так, чтобы возвращать вам ваши прошлые слова.
          </p>
        </div>

        <!-- Comparison Table -->
        <div class="overflow-x-auto">
          <table class="w-full border-collapse text-left font-sans text-sm">
            <thead>
              <tr class="border-b border-border-color font-mono text-[11px] tracking-widest uppercase text-text-muted">
                <th class="py-4 pr-6">Инструмент</th>
                <th class="py-4 px-6">Что делает</th>
                <th class="py-4 pl-6">Чего по своей природе не делает</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border-color">
              <tr>
                <td class="py-5 pr-6 font-semibold text-text-primary">Дневник</td>
                <td class="py-5 px-6 text-text-secondary">Хранит ваши мысли.</td>
                <td class="py-5 pl-6 text-text-muted">Сам не показывает изменения между отдельными периодами.</td>
              </tr>
              <tr>
                <td class="py-5 pr-6 font-semibold text-text-primary">ИИ-ассистент</td>
                <td class="py-5 px-6 text-text-secondary">Помогает разобраться с сегодняшней ситуацией.</td>
                <td class="py-5 pl-6 text-text-muted">Не возвращает вас к вашим мыслям из прошлого и не сопоставляет их во времени.</td>
              </tr>
              <tr>
                <td class="py-5 pr-6 font-semibold text-text-primary">Трекер</td>
                <td class="py-5 px-6 text-text-secondary">Фиксирует выполнение целей и привычек.</td>
                <td class="py-5 pl-6 text-text-muted">Показывает действия и статистику, но не показывает изменение мыслей и поведения.</td>
              </tr>
              <tr class="bg-card-surface/70">
                <td class="py-5 pr-6 font-display font-semibold text-accent flex items-center gap-2">
                  <span class="w-2 h-2 rounded-full bg-accent"></span>
                  ForwardTrace
                </td>
                <td class="py-5 px-6 font-medium text-text-primary">
                  Сохраняет ежедневные мысли через естественные голосовые записи и помогает увидеть изменения во времени.
                </td>
                <td class="py-5 pl-6 text-accent">
                  Не оценивает вас и не считает проценты. Вывод остаётся за вами.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

      </div>
    </section>

    <!-- SECTION 4: 3 ПРИНЦИПА -->
    <section class="py-20 md:py-32 border-t border-border-color">
      <div class="max-w-[1200px] mx-auto px-6">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          
          <div class="p-8 rounded-3xl bg-card-bg border border-border-color">
            <span class="font-mono text-sm font-bold text-accent mb-4 block">01</span>
            <h3 class="font-display font-medium text-xl text-text-primary mb-3">Без рутины</h3>
            <p class="font-sans text-sm text-text-secondary leading-relaxed">
              Не нужно каждый день заполнять десятки полей или подбирать правильные категории.
            </p>
          </div>

          <div class="p-8 rounded-3xl bg-card-bg border border-border-color">
            <span class="font-mono text-sm font-bold text-accent mb-4 block">02</span>
            <h3 class="font-display font-medium text-xl text-text-primary mb-3">Голосом</h3>
            <p class="font-sans text-sm text-text-secondary leading-relaxed">
              Просто расскажите, как прошёл ваш день. Тридцать секунд в конце дня — этого достаточно.
            </p>
          </div>

          <div class="p-8 rounded-3xl bg-card-bg border border-border-color">
            <span class="font-mono text-sm font-bold text-accent mb-4 block">03</span>
            <h3 class="font-display font-medium text-xl text-text-primary mb-3">Изменения во времени</h3>
            <p class="font-sans text-sm text-text-secondary leading-relaxed">
              Мы возвращаем ваши прошлые мысли, чтобы вы могли увидеть то, что обычно забывается.
            </p>
          </div>

        </div>
      </div>
    </section>

    <!-- FINAL CALL TO ACTION -->
    <section class="py-24 md:py-36 border-t border-border-color bg-card-surface/40 relative">
      <div class="max-w-[800px] mx-auto px-6 text-center">
        
        <h2 class="font-display font-semibold text-[28px] md:text-[40px] tracking-tight text-text-primary mb-6">
          А каким вы станете через несколько месяцев?
        </h2>
        
        <p class="font-sans text-[18px] text-text-secondary mb-10 max-w-[500px] mx-auto">
          Первая запись занимает тридцать секунд. Начать можно прямо сейчас в браузере.
        </p>

        <div class="flex flex-wrap items-center justify-center gap-4">
          <button
            @click="openRecordingModal"
            class="flex items-center gap-3 px-8 py-4 rounded-2xl bg-accent text-[#0A1022] font-sans font-semibold text-[16px] shadow-xl shadow-accent/20 hover:bg-accent-hover hover:text-[#FFFFFF] transition-all active:scale-95"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="22"></line>
            </svg>
            Записать сейчас (30 сек)
          </button>

          <router-link
            to="/today"
            class="px-8 py-4 rounded-2xl border border-border-strong bg-card-bg hover:bg-card-surface text-text-primary font-sans font-medium text-[16px] transition-all"
          >
            Перейти в кабинет
          </router-link>
        </div>

        <p class="font-mono text-xs text-text-muted mt-6">
          Регистрация открыта · Начать можно бесплатно
        </p>

      </div>
    </section>

    <!-- FOOTER -->
    <footer class="py-16 border-t border-border-color bg-bg-primary text-text-muted font-sans text-xs">
      <div class="max-w-[1200px] mx-auto px-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-8">
        <div>
          <div class="flex items-center gap-2 text-text-primary mb-2">
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" focusable="false" class="text-accent">
              <path d="M2 13.5 C5.5 13.5 5.5 4.5 9 4.5 C12.5 4.5 12.5 9 16 9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
              <circle cx="16" cy="9" r="2.2" fill="currentColor"/>
            </svg>
            <span class="font-display font-semibold text-[15px]">ForwardTrace</span>
          </div>
          <p class="max-w-[400px] text-text-secondary leading-relaxed">
            Расскажите день голосом. Через несколько месяцев увидите свои же слова рядом.
          </p>
        </div>

        <div class="flex flex-wrap gap-8 font-mono text-[11px] uppercase tracking-wider">
          <a href="#recognize" class="hover:text-text-primary transition-colors">Как это выглядит</a>
          <a href="#moments" class="hover:text-text-primary transition-colors">Два момента</a>
          <a href="#compare" class="hover:text-text-primary transition-colors">Сравнение</a>
          <router-link to="/today" class="hover:text-text-primary transition-colors">Кабинет</router-link>
        </div>
      </div>
    </footer>

  </div>
</template>
