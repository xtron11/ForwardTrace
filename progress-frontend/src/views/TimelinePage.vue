<script setup lang="ts">
import { ref } from 'vue';
import BottomNav from '../components/BottomNav.vue';
import TopActions from '../components/TopActions.vue';
import AudioRecordingModal from '../components/AudioRecordingModal.vue';
import { useTimelineStore } from '../composables/useTimelineStore';

const { entries, removeEntry } = useTimelineStore();
const isRecordModalOpen = ref(false);

const openRecordModal = () => {
  isRecordModalOpen.value = true;
};

const closeRecordModal = () => {
  isRecordModalOpen.value = false;
};
</script>

<template>
  <div class="min-h-screen bg-bg-primary text-text-primary font-sans pb-28 relative antialiased">
    <TopActions />

    <!-- Audio Recording Modal -->
    <AudioRecordingModal
      :is-open="isRecordModalOpen"
      @close="closeRecordModal"
    />

    <div class="max-w-[680px] mx-auto px-6 pt-16">
      
      <!-- Top Header -->
      <div class="flex items-center justify-between mb-8 pb-4 border-b border-border-color">
        <div>
          <p class="font-mono text-[11px] tracking-widest uppercase text-text-muted">
            Хроника ваших дней
          </p>
          <h1 class="font-display font-semibold text-2xl sm:text-3xl text-text-primary mt-1">
            Записи и динамика
          </h1>
        </div>
        <button
          @click="openRecordModal"
          class="flex items-center gap-2 px-4 py-2 rounded-xl bg-accent text-[#0A1022] font-mono text-xs font-bold uppercase tracking-wider hover:bg-accent-hover hover:text-white transition-all shadow-md active:scale-95"
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
          Хроника &bull; Пока пусто
        </p>
        <h2 class="text-3xl sm:text-4xl font-display font-medium mb-6 leading-tight">
          Реестр начнётся<br/>с первой записи
        </h2>
        <p class="font-serif italic text-xl text-text-secondary mb-12 leading-relaxed max-w-[400px] mx-auto">
          «Тридцать секунд в конце дня — этого достаточно.»
        </p>
        
        <button
          @click="openRecordModal"
          class="bg-accent text-[#0A1022] font-mono text-[12px] tracking-widest uppercase font-bold px-8 py-4 rounded-2xl hover:bg-accent-hover hover:text-white transition-all shadow-xl shadow-accent/20"
        >
          Рассказать
        </button>
      </div>

      <!-- Entries List -->
      <div v-else class="space-y-6">
        <div
          v-for="entry in entries"
          :key="entry.id"
          class="bg-card-bg border border-border-color rounded-3xl p-6 sm:p-7 transition-all hover:border-border-strong relative group"
        >
          <!-- Entry Header -->
          <div class="flex items-center justify-between font-mono text-xs text-text-muted mb-4">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-accent"></span>
              <span class="font-semibold text-text-primary uppercase tracking-wider">{{ entry.date }}</span>
            </div>
            <div class="flex items-center gap-3">
              <span v-if="entry.duration > 0" class="text-[11px]">
                {{ entry.duration }} сек
              </span>
              <button
                @click="removeEntry(entry.id)"
                class="opacity-0 group-hover:opacity-100 text-text-muted hover:text-[#FF5C5C] p-1 transition-opacity"
                title="Удалить запись"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
              </button>
            </div>
          </div>

          <!-- Spoken words -->
          <div class="mb-4">
            <p class="font-mono text-[10px] tracking-widest uppercase text-text-muted mb-1.5">
              Сказано
            </p>
            <p class="font-sans text-[15px] text-text-primary leading-relaxed bg-card-surface/70 p-3.5 rounded-xl border border-border-color">
              {{ entry.saidText }}
            </p>
          </div>

          <!-- Extracted Fact -->
          <div class="border-l-2 border-accent pl-3.5 py-0.5">
            <p class="font-mono text-[10px] tracking-widest uppercase text-text-muted mb-1">
              Извлечено
            </p>
            <p class="font-serif italic text-[14px] text-text-secondary leading-snug">
              {{ entry.extractedFact }}
            </p>
          </div>

          <!-- Audio playback if present -->
          <div v-if="entry.audioUrl" class="mt-4 pt-3 border-t border-border-color flex items-center gap-3">
            <audio controls :src="entry.audioUrl" class="w-full h-8 rounded opacity-85"></audio>
          </div>
        </div>
      </div>

    </div>

    <BottomNav />
  </div>
</template>
