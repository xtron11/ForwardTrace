<script setup lang="ts">
import { ref, computed } from 'vue';
import { useTimelineStore } from '../composables/useTimelineStore';

const emit = defineEmits<{
  (e: 'open-record'): void;
}>();

const { totalDays, latestEntry, addEntry } = useTimelineStore();

const isTextInputOpen = ref(false);
const textNote = ref('');
const saveToast = ref(false);

const prompts = [
  'Что из сделанного сегодня действительно приблизило результат?',
  'О чем вы думали больше всего на протяжении дня?',
  'В чём было главное сопротивление и как вы с ним обошлись?',
  'Если бы сегодня нужно было запомнить одну мысль — какой бы она была?'
];
const promptIndex = ref(0);

const cyclePrompt = () => {
  promptIndex.value = (promptIndex.value + 1) % prompts.length;
};

const activePrompt = computed(() => prompts[promptIndex.value]);

const currentDateFormatted = computed(() => {
  const date = new Date();
  const days = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
  const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
  return `${days[date.getDay()]}, ${date.getDate()} ${months[date.getMonth()]}`;
});

const triggerRecord = () => {
  emit('open-record');
};

const handleSaveTextNote = () => {
  if (!textNote.value.trim()) return;
  const now = new Date();
  const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
  const formattedDate = `${now.getDate()} ${months[now.getMonth()]}`;

  addEntry({
    date: formattedDate,
    duration: 0,
    saidText: textNote.value.trim(),
    extractedFact: 'текстовая фиксация мыслей за день',
    goalContext: 'Цель · довести задуманное до результата',
  });

  textNote.value = '';
  isTextInputOpen.value = false;
  saveToast.value = true;
  setTimeout(() => {
    saveToast.value = false;
  }, 2500);
};
</script>

<template>
  <div class="w-full flex-1 flex flex-col justify-center items-center px-4 sm:px-6 py-4 sm:py-8 max-w-[620px] mx-auto antialiased">
    
    <!-- Top Content Group: Progress, Goal & Context -->
    <div class="w-full space-y-3.5">
      
      <!-- Top Date & Status Bar -->
      <div class="flex items-center justify-between">
        <p class="font-mono text-[11px] sm:text-xs tracking-wider uppercase text-text-muted flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-accent"></span>
          {{ currentDateFormatted }}
        </p>
        <span class="font-mono text-[10px] sm:text-[11px] uppercase tracking-wider text-accent bg-card-surface/90 border border-border-color px-3 py-1 rounded-full font-medium shadow-xs">
          Дневной статус
        </span>
      </div>

      <!-- Main Progress Hero Card (Motion Glass Card with glowing top accent line and deep shadow) -->
      <div class="bg-card-bg/90 backdrop-blur-xl border border-border-color rounded-2xl sm:rounded-3xl p-5 sm:p-6 shadow-xl relative overflow-hidden transition-all duration-300 hover:border-accent/40 hover:shadow-2xl">
        
        <!-- Subtle linear accent bar at top edge (as seen in the screenshot) -->
        <div class="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-transparent via-accent to-transparent opacity-85"></div>

        <div class="flex items-end justify-between mb-4">
          <div class="flex items-baseline gap-3">
            <span class="text-6xl sm:text-7xl font-display font-bold tracking-tighter text-text-primary leading-none">
              {{ totalDays }}
            </span>
            <div class="font-mono text-[11px] sm:text-xs tracking-wider uppercase text-text-muted leading-tight">
              {{ totalDays === 1 ? 'день' : (totalDays >= 2 && totalDays <= 4 ? 'дня' : 'дней') }}<br/>
              <span class="text-text-primary font-medium">в пути</span>
            </div>
          </div>

          <div class="text-right font-mono text-[11px] sm:text-xs">
            <span class="text-accent font-semibold text-sm">{{ totalDays }} / 14</span>
            <span class="text-text-muted uppercase tracking-wider ml-1.5">дней</span>
          </div>
        </div>

        <!-- 14-Day Progress Bar Segments with dynamic active gradient -->
        <div class="flex gap-1.5 sm:gap-2 mb-2.5">
          <div
            v-for="i in 14"
            :key="i"
            class="h-2 sm:h-2.5 flex-1 rounded-sm transition-all duration-500"
            :class="i <= totalDays ? 'bg-gradient-to-t from-accent-hover to-accent shadow-sm shadow-accent/40' : 'bg-card-surface border border-border-color/60'"
            :title="`День ${i}`"
          ></div>
        </div>

        <div class="flex justify-between items-center font-mono text-[10px] sm:text-[11px] tracking-wider uppercase text-text-muted">
          <span>Текущий цикл динамики</span>
          <span class="text-text-primary font-medium">{{ Math.min(100, Math.round((totalDays / 14) * 100)) }}% завершено</span>
        </div>

        <!-- Purpose Banner Embedded Inside Card -->
        <div class="mt-4 pt-3.5 border-t border-border-color/80 flex items-start gap-3">
          <div class="w-2 h-2 rounded-full bg-accent mt-1.5 shrink-0"></div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-text-muted mb-1">
              <span>Главная цель</span>
              <router-link to="/goals" class="text-accent hover:underline lowercase font-sans text-xs flex items-center gap-1 font-medium">
                цели →
              </router-link>
            </div>
            <p class="font-serif italic text-sm sm:text-base text-text-secondary leading-snug line-clamp-2">
              «Научиться самостоятельно развертывать сети и довести задуманное до результата без спешки.»
            </p>
          </div>
        </div>

      </div>

      <!-- Quick Recent Observation (If exists) -->
      <div v-if="latestEntry" class="bg-card-bg/80 backdrop-blur-md border border-border-color rounded-xl sm:rounded-2xl px-4 py-2.5 flex items-center justify-between text-xs shadow-sm">
        <div class="flex items-center gap-2.5 truncate pr-3">
          <span class="font-mono text-[10px] uppercase tracking-wider text-accent shrink-0 font-medium">Предыдущий факт:</span>
          <span class="font-serif italic text-text-secondary truncate text-xs sm:text-sm">
            «{{ latestEntry.extractedFact || latestEntry.saidText }}»
          </span>
        </div>
        <router-link to="/timeline" class="font-mono text-[10px] sm:text-[11px] text-text-muted hover:text-accent shrink-0 uppercase tracking-wider font-semibold">
          Хроника →
        </router-link>
      </div>

    </div>

    <!-- Central Audio Action Stage -->
    <div class="w-full flex flex-col items-center justify-center text-center my-6 sm:my-8">
      
      <h2 class="text-xl sm:text-3xl font-display font-semibold mb-1.5 leading-tight text-text-primary tracking-tight">
        {{ totalDays === 0 ? 'Реестр начнётся с первой записи' : 'Зафиксируйте сегодняшний день' }}
      </h2>
      <p class="font-sans text-xs sm:text-sm text-text-secondary max-w-sm mb-6 leading-relaxed">
        Расскажите о том, что произошло на самом деле. Говорите свободно, сколько нужно.
      </p>

      <!-- Static Clean Recording Button with soft subtle aura glow -->
      <div class="relative flex items-center justify-center">
        <!-- Soft subtle atmospheric glow behind button -->
        <div class="absolute w-36 h-36 sm:w-44 sm:h-44 rounded-full bg-accent/15 blur-xl pointer-events-none"></div>

        <button
          @click="triggerRecord"
          class="relative z-10 w-28 h-28 sm:w-36 sm:h-36 bg-accent rounded-full flex flex-col items-center justify-center text-[#0A1022] shadow-xl shadow-accent/25 hover:bg-accent-hover hover:text-white transition-all duration-200 cursor-pointer active:scale-95"
          aria-label="Начать запись"
        >
          <!-- Mic icon -->
          <div class="w-5 h-5 sm:w-6 sm:h-6 mb-1.5 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="22"></line>
            </svg>
          </div>

          <span class="font-mono text-xs sm:text-sm tracking-widest uppercase font-bold">
            Записать
          </span>
          <span class="font-mono text-[9px] sm:text-[10px] opacity-80 mt-0.5">
            голосом
          </span>
        </button>
      </div>

      <!-- Alternative text note toggle -->
      <button
        @click="isTextInputOpen = !isTextInputOpen"
        class="font-mono text-xs tracking-wider uppercase text-text-muted hover:text-accent transition-colors mt-5 underline decoration-dotted underline-offset-4"
      >
        {{ isTextInputOpen ? 'скрыть поле ввода' : 'написать текстом' }}
      </button>

      <!-- Collapsible Text Note Drawer -->
      <div
        v-if="isTextInputOpen"
        class="w-full max-w-md bg-card-bg border border-border-color rounded-2xl p-4 sm:p-5 mt-3 text-left shadow-lg transition-colors"
      >
        <label class="block font-mono text-[10px] uppercase tracking-wider text-text-muted mb-2 font-medium">
          Текстовая заметка дня
        </label>
        <textarea
          v-model="textNote"
          rows="3"
          placeholder="Что произошло сегодня? Какая мысль или действие были главными?"
          class="w-full bg-card-surface border border-border-color rounded-xl p-3 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent resize-none font-sans"
        ></textarea>
        <div class="flex justify-end gap-2.5 mt-3">
          <button
            @click="isTextInputOpen = false"
            class="px-3.5 py-1.5 rounded-lg text-xs font-mono text-text-muted hover:text-text-primary"
          >
            Отмена
          </button>
          <button
            @click="handleSaveTextNote"
            class="px-4 py-1.5 rounded-lg bg-accent text-[#0A1022] text-xs font-mono font-bold uppercase tracking-wider hover:bg-accent-hover hover:text-white transition-colors"
          >
            Сохранить
          </button>
        </div>
      </div>

      <!-- Success Toast -->
      <div
        v-if="saveToast"
        class="mt-3 px-4 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono text-xs uppercase tracking-wider flex items-center gap-2"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 6 9 17l-5-5"></path>
        </svg>
        Запись сохранена в хронологию
      </div>

    </div>

  </div>
</template>
