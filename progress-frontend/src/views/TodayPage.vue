<script setup lang="ts">
import { ref, computed } from 'vue';
import BottomNav from '../components/BottomNav.vue';
import TopActions from '../components/TopActions.vue';
import AudioRecordingModal from '../components/AudioRecordingModal.vue';
import { useTimelineStore } from '../composables/useTimelineStore';

const { totalDays, latestEntry, addEntry } = useTimelineStore();

const isRecordModalOpen = ref(false);
const isTextInputOpen = ref(false);
const textNote = ref('');

const openRecordModal = () => {
  isRecordModalOpen.value = true;
};

const closeRecordModal = () => {
  isRecordModalOpen.value = false;
};

const currentDateFormatted = computed(() => {
  const date = new Date();
  const days = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
  const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
  return `${days[date.getDay()]}, ${date.getDate()} ${months[date.getMonth()]}`;
});

const handleSaveTextNote = () => {
  if (!textNote.value.trim()) return;
  const now = new Date();
  const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
  const formattedDate = `${now.getDate()} ${months[now.getMonth()]}`;

  addEntry({
    date: formattedDate,
    duration: 0,
    saidText: textNote.value.trim(),
    extractedFact: 'текстовая запись мыслей за день',
    goalContext: 'Цель · довести задуманное до результата',
  });

  textNote.value = '';
  isTextInputOpen.value = false;
};
</script>

<template>
  <div class="min-h-screen bg-bg-primary text-text-primary font-sans pb-28 relative overflow-x-hidden antialiased">
    <TopActions />

    <!-- Audio Recording Modal -->
    <AudioRecordingModal
      :is-open="isRecordModalOpen"
      @close="closeRecordModal"
    />

    <div class="max-w-[700px] mx-auto px-6 pt-12">
      <!-- Date Header -->
      <p class="font-mono text-[11px] tracking-widest uppercase text-text-muted mb-4">
        {{ currentDateFormatted }}
      </p>

      <!-- Days In Journey -->
      <div class="flex items-baseline gap-4 mb-10">
        <span class="text-7xl sm:text-9xl font-sans font-semibold tracking-tighter text-text-primary">
          {{ totalDays }}
        </span>
        <div class="font-mono text-[11px] tracking-widest uppercase text-text-muted leading-relaxed">
          дней<br/>ты в пути
        </div>
      </div>

      <!-- 14-Day Progress Blocks -->
      <div class="flex gap-1.5 mb-3">
        <div
          v-for="i in 14"
          :key="i"
          class="h-2 flex-1 rounded-sm transition-all"
          :class="i <= totalDays ? 'bg-accent shadow-sm shadow-accent/20' : 'bg-border-color'"
        ></div>
      </div>
      <p class="font-mono text-[10px] tracking-widest uppercase text-text-muted mb-12 flex justify-between">
        <span>Последние 14 дней</span>
        <span class="text-accent">{{ totalDays }} / 14 заполнено</span>
      </p>

      <!-- Purpose Quote (Left intentionally blank as requested by user) -->
      <div class="border-l-2 border-accent pl-5 mb-16 py-1 bg-card-bg/40 rounded-r-2xl border-y border-r border-border-color">
        <p class="font-mono text-[10px] tracking-widest uppercase text-text-muted mb-2">Ради чего ты начал</p>
        <p class="font-serif italic text-lg sm:text-xl text-text-secondary leading-relaxed min-h-[28px]">
          <!-- Оставлено пустым для чтения из БД/памяти как просил пользователь -->
        </p>
      </div>

      <!-- Record Section -->
      <div class="flex flex-col items-center justify-center text-center mt-6">
        <h2 class="text-2xl sm:text-3xl font-display font-medium mb-10 leading-tight text-text-primary">
          {{ totalDays === 0 ? 'Реестр начнётся с первой записи' : 'Зафиксируйте сегодняшний день' }}
        </h2>

        <!-- The Big Pulse Voice Button -->
        <div class="relative flex items-center justify-center">
          <div class="absolute w-56 h-56 sm:w-64 sm:h-64 rounded-full bg-accent/15 animate-ping opacity-30 pointer-events-none"></div>
          <button
            @click="openRecordModal"
            class="group relative z-10 w-44 h-44 sm:w-52 sm:h-52 bg-accent rounded-full flex flex-col items-center justify-center text-[#0A1022] shadow-2xl shadow-accent/30 hover:scale-[1.03] active:scale-95 transition-all"
            aria-label="Начать запись"
          >
            <div class="w-4 h-4 bg-[#0A1022] rounded-full mb-3 group-hover:scale-125 transition-transform"></div>
            <span class="font-mono text-[12px] tracking-widest uppercase font-bold">Говорить</span>
            <span class="font-mono text-[10px] text-[#0A1022]/70 mt-1">30 сек</span>
          </button>
        </div>

        <p class="font-mono text-[11px] tracking-widest text-text-muted mt-8">
          30 секунд &bull; можно сбивчиво
        </p>

        <!-- Write Text Option -->
        <button
          @click="isTextInputOpen = !isTextInputOpen"
          class="font-mono text-[11px] tracking-widest uppercase text-text-muted hover:text-accent transition-colors mt-12 mb-8 underline decoration-dotted underline-offset-4"
        >
          {{ isTextInputOpen ? 'скрыть поле ввода' : 'написать текстом' }}
        </button>

        <!-- Inline Text Input Drawer -->
        <div v-if="isTextInputOpen" class="w-full max-w-md bg-card-bg border border-border-color rounded-2xl p-5 mb-8 text-left transition-all">
          <label class="block font-mono text-[10px] uppercase tracking-wider text-text-muted mb-2">
            Запись мыслей за день
          </label>
          <textarea
            v-model="textNote"
            rows="3"
            placeholder="Что произошло сегодня? Как вы себя чувствовали?"
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

      </div>
    </div>

    <BottomNav />
  </div>
</template>
