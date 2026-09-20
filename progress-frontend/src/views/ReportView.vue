<script setup lang="ts">
import { ref } from 'vue';
import { useTimelineStore } from '../composables/useTimelineStore';

const emit = defineEmits<{
  (e: 'open-record'): void;
}>();

const { entries, totalDays } = useTimelineStore();

const isReportGenerated = ref(totalDays.value >= 2);
const isGenerating = ref(false);

const generateReport = () => {
  isGenerating.value = true;
  setTimeout(() => {
    isGenerating.value = false;
    isReportGenerated.value = true;
  }, 700);
};

const triggerRecord = () => {
  emit('open-record');
};
</script>

<template>
  <div class="w-full flex-1 flex flex-col justify-start px-6 py-8 md:py-12 max-w-[760px] mx-auto antialiased">
    
    <!-- Top Header -->
    <div class="mb-10 pb-6 border-b border-border-color">
      <p class="font-mono text-[11px] tracking-widest uppercase text-text-muted">
        Синтез и аналитика · ForwardTrace
      </p>
      <h1 class="font-display font-semibold text-2xl sm:text-3xl text-text-primary mt-1">
        Отчёты динамики
      </h1>
      <p class="font-sans text-sm text-text-secondary mt-2">
        Сравнение ваших слов из прошлого с тем, что вы говорите сейчас.
      </p>
    </div>

    <!-- Generated Report State -->
    <div v-if="isReportGenerated" class="space-y-8">
      
      <!-- Primary Report Card -->
      <article class="bg-card-bg border border-border-color rounded-3xl p-6 sm:p-9 shadow-md relative overflow-hidden">
        
        <!-- Header Info -->
        <div class="flex flex-wrap items-center justify-between gap-3 pb-6 border-b border-border-color mb-6">
          <div>
            <span class="font-mono text-[11px] uppercase tracking-widest text-accent font-semibold block">
              Срез № 1 · Двухнедельный цикл
            </span>
            <span class="font-sans text-sm text-text-muted">
              Период: 14 февраля — 28 февраля
            </span>
          </div>

          <span class="px-3 py-1 rounded-full bg-card-surface border border-border-color font-mono text-[11px] text-text-primary">
            Готов к анализу
          </span>
        </div>

        <!-- Comparative Two Moments Quote Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          
          <div class="p-5 rounded-2xl bg-card-surface/60 border border-border-color">
            <span class="font-mono text-[10px] tracking-widest uppercase text-text-muted block mb-2">
              Точка А · 14 февраля
            </span>
            <p class="font-serif italic text-sm text-text-primary leading-relaxed">
              «Я вообще не понимаю, что мне делать дальше. Сил ни на что нет. Уже несколько дней просто откладываю всё на потом…»
            </p>
          </div>

          <div class="p-5 rounded-2xl bg-card-surface/60 border border-accent/40">
            <span class="font-mono text-[10px] tracking-widest uppercase text-accent block mb-2">
              Точка Б · 28 февраля
            </span>
            <p class="font-serif italic text-sm text-text-primary leading-relaxed">
              «Сегодня я снова был без сил. Хотел вообще ничего не делать. Но всё-таки сел и позанимался…»
            </p>
          </div>

        </div>

        <!-- What ForwardTrace Noticed -->
        <div class="p-6 rounded-2xl bg-card-surface border border-border-color mb-6">
          <p class="font-mono text-[10px] tracking-widest uppercase text-accent mb-2">
            Что заметил ForwardTrace
          </p>
          <p class="font-serif italic text-base sm:text-lg text-text-primary leading-relaxed">
            «Две недели назад вы писали, что не знаете, что делать дальше, и что сил ни на что нет. Сегодня сил снова не было — но вы всё равно сели и позанимались.»
          </p>
        </div>

        <!-- Key Observations Checklist -->
        <div class="space-y-3 pt-4 border-t border-border-color">
          <p class="font-mono text-[10px] tracking-widest uppercase text-text-muted mb-3">
            Ключевые сдвиги в формулировках:
          </p>

          <div class="flex items-start gap-3 text-sm text-text-secondary">
            <span class="w-1.5 h-1.5 rounded-full bg-accent mt-2 shrink-0"></span>
            <p><strong class="text-text-primary font-medium">Снижение внутреннего сопротивления:</strong> переход от полной пассивности («откладываю всё») к действию через усталость («всё-таки сел»).</p>
          </div>

          <div class="flex items-start gap-3 text-sm text-text-secondary">
            <span class="w-1.5 h-1.5 rounded-full bg-accent mt-2 shrink-0"></span>
            <p><strong class="text-text-primary font-medium">Фиксация фактов вместо эмоций:</strong> в записях стало на 40% больше конкретных глаголов действия.</p>
          </div>
        </div>

      </article>

      <!-- Refresh / Re-run Action -->
      <div class="flex justify-between items-center text-xs font-mono text-text-muted pt-2">
        <span>Отчёт фиксируется один раз и сохраняется</span>
        <button
          @click="generateReport"
          :disabled="isGenerating"
          class="hover:text-accent uppercase tracking-wider transition-colors underline decoration-dotted"
        >
          {{ isGenerating ? 'Анализирую...' : 'Обновить срез' }}
        </button>
      </div>

    </div>

    <!-- Empty / Waiting State -->
    <div v-else class="max-w-[540px] mx-auto text-center py-12">
      <div class="w-16 h-16 rounded-2xl bg-card-surface border border-border-color mx-auto flex items-center justify-center text-accent mb-6">
        <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" x2="8" y1="13" y2="13"/>
          <line x1="16" x2="8" y1="17" y2="17"/>
        </svg>
      </div>

      <h2 class="text-2xl sm:text-3xl font-display font-medium mb-4 text-text-primary">
        Отчёта пока нет
      </h2>
      
      <p class="font-serif text-base sm:text-lg text-text-secondary mb-8 leading-relaxed text-left mx-auto">
        Первый отчёт приходит на третий день, дальше по одному в неделю. Нужна пара записей, чтобы ему было о чём говорить. Каждый пишется один раз и сохраняется — при повторном заходе текст не изменится.
      </p>

      <div class="flex flex-wrap items-center justify-center gap-4">
        <button
          @click="generateReport"
          :disabled="isGenerating"
          class="bg-accent text-[#0A1022] font-mono text-[12px] tracking-widest uppercase font-bold px-7 py-3.5 rounded-xl hover:bg-accent-hover hover:text-[#FFFFFF] transition-all shadow-lg shadow-accent/20 active:scale-95"
        >
          {{ isGenerating ? 'Сборка...' : 'Собрать отчёт сейчас' }}
        </button>

        <button
          @click="triggerRecord"
          class="border border-border-color bg-card-surface text-text-primary font-mono text-[12px] tracking-widest uppercase px-6 py-3.5 rounded-xl hover:border-accent transition-colors"
        >
          Сделать запись
        </button>
      </div>
    </div>

  </div>
</template>
