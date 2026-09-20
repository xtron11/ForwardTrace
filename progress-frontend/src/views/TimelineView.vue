<script setup lang="ts">
import { useTimelineStore } from '../composables/useTimelineStore';

const emit = defineEmits<{
  (e: 'open-record'): void;
}>();

const { entries, totalDays, removeEntry } = useTimelineStore();

const triggerRecord = () => {
  emit('open-record');
};
</script>

<template>
  <div class="w-full flex-1 flex flex-col justify-start px-6 py-8 md:py-12 max-w-[760px] mx-auto antialiased">
    
    <!-- Header with Quick Record Button -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8 pb-6 border-b border-border-color">
      <div>
        <p class="font-mono text-[11px] tracking-widest uppercase text-text-muted">
          Хроника ваших дней · {{ totalDays }} записей
        </p>
        <h1 class="font-display font-semibold text-2xl sm:text-3xl text-text-primary mt-1">
          Записи и динамика
        </h1>
      </div>

      <button
        @click="triggerRecord"
        class="self-start sm:self-auto flex items-center gap-2 px-4 py-2.5 rounded-xl bg-accent text-[#0A1022] font-mono text-xs font-bold uppercase tracking-wider hover:bg-accent-hover hover:text-[#FFFFFF] transition-all shadow-md active:scale-95"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
          <line x1="12" y1="19" x2="12" y2="22"></line>
        </svg>
        Рассказать
      </button>
    </div>

    <!-- Empty State -->
    <div v-if="entries.length === 0" class="pt-16 text-center">
      <p class="font-mono text-[11px] tracking-widest uppercase text-text-muted mb-4">
        Хроника · Пока пусто
      </p>
      <h2 class="text-3xl sm:text-4xl font-display font-medium mb-6 leading-tight">
        Реестр начнётся<br/>с первой записи
      </h2>
      <p class="font-serif italic text-xl text-text-secondary mb-12 leading-relaxed max-w-[400px] mx-auto">
        «Тридцать секунд в конце дня — этого достаточно.»
      </p>
      
      <button
        @click="triggerRecord"
        class="bg-accent text-[#0A1022] font-mono text-[12px] tracking-widest uppercase font-bold px-8 py-4 rounded-2xl hover:bg-accent-hover hover:text-[#FFFFFF] transition-all shadow-xl shadow-accent/20"
      >
        Записать первую мысль
      </button>
    </div>

    <!-- Timeline Entries List -->
    <div v-else class="space-y-6">
      <article
        v-for="entry in entries"
        :key="entry.id"
        class="bg-card-bg border border-border-color rounded-3xl p-6 sm:p-7 transition-all hover:border-border-strong relative group shadow-sm"
      >
        <!-- Entry Top Metadata Bar -->
        <div class="flex items-center justify-between font-mono text-xs text-text-muted mb-4">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-accent"></span>
            <span class="font-semibold text-text-primary uppercase tracking-wider">{{ entry.date }}</span>
          </div>
          
          <div class="flex items-center gap-3">
            <span v-if="entry.duration > 0" class="text-[11px] bg-card-surface px-2 py-0.5 rounded border border-border-color">
              {{ entry.duration }} сек
            </span>
            <button
              @click="removeEntry(entry.id)"
              class="opacity-60 sm:opacity-0 group-hover:opacity-100 text-text-muted hover:text-[#FF5C5C] p-1.5 rounded hover:bg-card-surface transition-all"
              title="Удалить запись"
              aria-label="Удалить запись"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </div>
        </div>

        <!-- Spoken Text Block -->
        <div class="mb-4">
          <p class="font-mono text-[10px] tracking-widest uppercase text-text-muted mb-1.5">
            Сказано
          </p>
          <p class="font-sans text-[15px] text-text-primary leading-relaxed bg-card-surface/70 p-4 rounded-xl border border-border-color">
            {{ entry.saidText }}
          </p>
        </div>

        <!-- Extracted Fact Block -->
        <div class="border-l-2 border-accent pl-3.5 py-0.5">
          <p class="font-mono text-[10px] tracking-widest uppercase text-text-muted mb-1">
            Извлечено
          </p>
          <p class="font-serif italic text-[15px] text-text-secondary leading-snug">
            {{ entry.extractedFact }}
          </p>
        </div>

        <!-- Goal context if any -->
        <div v-if="entry.goalContext" class="mt-4 pt-3 border-t border-border-color flex justify-between items-center text-[11px] font-mono text-text-muted">
          <span>{{ entry.goalContext }}</span>
        </div>

        <!-- Audio Player if Audio Present -->
        <div v-if="entry.audioUrl" class="mt-4 pt-3 border-t border-border-color">
          <audio controls :src="entry.audioUrl" class="w-full h-8 rounded opacity-85"></audio>
        </div>
      </article>
    </div>

  </div>
</template>
