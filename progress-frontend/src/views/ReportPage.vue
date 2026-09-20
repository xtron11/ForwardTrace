<script setup lang="ts">
import BottomNav from '../components/BottomNav.vue';
import TopActions from '../components/TopActions.vue';
</script>

<template>
  <div class="min-h-screen bg-bg-primary text-text-primary font-sans pb-24 relative flex flex-col justify-center">
    <TopActions />
    
    <div class="max-w-[500px] mx-auto px-6 text-center">
      <h1 class="text-3xl sm:text-4xl font-sans font-medium mb-6">Отчёта пока нет</h1>
      
      <p class="font-serif text-lg text-text-secondary mb-10 leading-relaxed text-left mx-auto">
        Первый отчёт приходит на третий день, дальше по одному в неделю. Нужна пара записей, чтобы ему было о чём говорить. Каждый пишется один раз и сохраняется — при повторном заходе текст не изменится.
      </p>
      
      <button class="bg-accent text-[#FFFFFF] font-mono text-[11px] tracking-widest uppercase px-8 py-4 rounded hover:bg-accent-hover transition-colors">
        Собрать отчёт
      </button>
    </div>

    <BottomNav />
  </div>
</template>
