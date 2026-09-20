<script setup lang="ts">
import { ref, computed } from 'vue';
import { useTimelineStore } from '../composables/useTimelineStore';

const emit = defineEmits<{
  (e: 'open-record'): void;
}>();

const { totalDays, addEntry } = useTimelineStore();

const isTextInputOpen = ref(false);
const textNote = ref('');
const saveToast = ref(false);

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
  <div class="w-full flex-1 flex flex-col justify-start px-6 py-8 md:py-12 max-w-[760px] mx-auto antialiased">
    
    <!-- Top Metadata Bar -->
    <div class="flex items-center justify-between mb-4">
      <p class="font-mono text-[11px] tracking-widest uppercase text-text-muted">
        {{ currentDateFormatted }}
      </p>
      <span class="font-mono text-[10px] uppercase tracking-wider text-accent bg-card-surface border border-border-color px-2.5 py-0.5 rounded-full">
        Сегодняшний срез
      </span>
    </div>

    <!-- Days in Journey Counter -->
    <div class="flex items-baseline gap-4 mb-8">
      <span class="text-7xl sm:text-8xl md:text-9xl font-display font-bold tracking-tighter text-text-primary leading-none">
        {{ totalDays }}
      </span>
      <div class="font-mono text-[11px] tracking-widest uppercase text-text-muted leading-relaxed">
        дней<br/>ты в пути
      </div>
    </div>

    <!-- 14-Day Progress Bar Units -->
    <div class="flex gap-1.5 mb-2.5">
      <div
        v-for="i in 14"
        :key="i"
        class="h-2 flex-1 rounded-xs transition-all duration-300"
        :class="i <= totalDays ? 'bg-accent shadow-sm shadow-accent/20' : 'bg-border-color'"
        :title="`День ${i}`"
      ></div>
    </div>
    <div class="flex justify-between items-center font-mono text-[10px] tracking-widest uppercase text-text-muted mb-12">
      <span>Цикл · 14 дней</span>
      <span class="text-accent font-semibold">{{ totalDays }} / 14 заполнено</span>
    </div>

    <!-- Purpose Quote Banner -->
    <div class="border-l-2 border-accent pl-5 py-3 mb-14 bg-card-surface/40 rounded-r-2xl border-y border-r border-border-color relative">
      <p class="font-mono text-[10px] tracking-widest uppercase text-text-muted mb-1.5">
        Ради чего ты начал
      </p>
      <p class="font-serif italic text-lg sm:text-xl text-text-secondary leading-relaxed min-h-[28px]">
        «Научиться самостоятельно развертывать сети и довести задуманное до результата без спешки.»
      </p>
    </div>

    <!-- Central Audio Action Stage -->
    <div class="flex flex-col items-center justify-center text-center my-4">
      <h2 class="text-2xl sm:text-3xl font-display font-semibold mb-3 leading-tight text-text-primary">
        {{ totalDays === 0 ? 'Реестр начнётся с первой записи' : 'Зафиксируйте сегодняшний день' }}
      </h2>
      <p class="font-sans text-sm text-text-secondary max-w-md mb-10">
        Тридцать секунд в конце дня — расскажите о том, что произошло на самом деле.
      </p>

      <!-- Big Pulse Voice Button -->
      <div class="relative flex items-center justify-center">
        <!-- Ambient pulsating glow waves -->
        <div class="absolute w-52 h-52 sm:w-60 sm:h-60 rounded-full bg-accent/15 animate-ping opacity-25 pointer-events-none"></div>
        <div class="absolute w-44 h-44 sm:w-52 sm:h-52 rounded-full bg-accent/20 transition-transform duration-700 pointer-events-none"></div>

        <button
          @click="triggerRecord"
          class="group relative z-10 w-40 h-40 sm:w-48 sm:h-48 bg-accent rounded-full flex flex-col items-center justify-center text-[#0A1022] shadow-2xl shadow-accent/30 hover:scale-[1.03] active:scale-95 transition-all"
          aria-label="Начать запись"
        >
          <div class="w-3.5 h-3.5 bg-[#0A1022] rounded-full mb-2.5 group-hover:scale-125 transition-transform"></div>
          <span class="font-mono text-[12px] tracking-widest uppercase font-bold">Говорить</span>
          <span class="font-mono text-[10px] text-[#0A1022]/70 mt-1">30 сек</span>
        </button>
      </div>

      <p class="font-mono text-[11px] tracking-widest text-text-muted mt-8">
        30 секунд · говорите свободно, можно сбивчиво
      </p>

      <!-- Alternative text note toggle -->
      <button
        @click="isTextInputOpen = !isTextInputOpen"
        class="font-mono text-[11px] tracking-widest uppercase text-text-muted hover:text-accent transition-colors mt-10 mb-4 underline decoration-dotted underline-offset-4"
      >
        {{ isTextInputOpen ? 'скрыть поле ввода' : 'написать текстом' }}
      </button>

      <!-- Collapsible Text Note Drawer -->
      <div
        v-if="isTextInputOpen"
        class="w-full max-w-md bg-card-bg border border-border-color rounded-2xl p-5 mt-2 text-left shadow-lg"
      >
        <label class="block font-mono text-[10px] uppercase tracking-wider text-text-muted mb-2">
          Текстовая заметка дня
        </label>
        <textarea
          v-model="textNote"
          rows="3"
          placeholder="Что произошло сегодня? Какая мысль или действие были главными?"
          class="w-full bg-card-surface border border-border-color rounded-xl p-3 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent resize-none font-sans"
        ></textarea>
        <div class="flex justify-end gap-2 mt-3">
          <button
            @click="isTextInputOpen = false"
            class="px-3 py-1.5 rounded-lg text-xs font-mono text-text-muted hover:text-text-primary"
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
        class="mt-4 px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono text-xs uppercase tracking-wider flex items-center gap-2"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 6 9 17l-5-5"></path>
        </svg>
        Запись сохранена в хронологию
      </div>

    </div>

  </div>
</template>
