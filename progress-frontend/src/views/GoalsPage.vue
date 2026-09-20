<script setup lang="ts">
import BottomNav from '../components/BottomNav.vue';
import TopActions from '../components/TopActions.vue';
</script>

<template>
  <div class="min-h-screen bg-bg-primary text-text-primary font-sans pb-24 relative">
    <TopActions />
    
    <div class="max-w-[750px] mx-auto px-6 pt-24">
      <h1 class="text-4xl sm:text-5xl font-sans font-medium mb-4">Над чем ты работаешь</h1>
      <p class="font-serif text-xl text-text-secondary mb-12 leading-relaxed">
        Одна запись покрывает все цели сразу.<br/>Расскажи, как прошёл день, и каждая часть попадёт к своей цели.
      </p>

      <!-- Goal Card -->
      <div class="border border-border-color bg-transparent p-6 sm:p-10 rounded-sm mb-8">
        <div class="flex flex-col sm:flex-row justify-between items-start gap-6 mb-6">
          <h2 class="text-2xl sm:text-[26px] font-sans font-medium leading-[1.3] flex-1">
            Развертывать вручную серверы и разные сервисы интегрировать внутрь. Научиться самостоятельно развертывать сети и настраивать сетевую инфраструктуру, а так же добавлять новые точки внутри сети
          </h2>
          <div class="flex gap-4 font-mono text-[10px] tracking-widest uppercase text-text-muted shrink-0 pt-2">
            <button class="border-b border-text-muted hover:text-text-primary transition-colors">Изменить</button>
            <button class="border-b border-text-muted hover:text-text-primary transition-colors">В архив</button>
          </div>
        </div>

        <p class="font-serif italic text-[19px] text-text-secondary mb-10 leading-relaxed">
          «Для меня важно построить устойчивую и стабильную карьеру в сфере IT, по направлению инженера, системного администратора или информационная безопасность»
        </p>

        <div class="border-t border-border-color pt-8">
          <p class="font-mono text-[10px] tracking-widest uppercase text-text-muted mb-5">Прогресс — это</p>
          <ul class="space-y-3 font-serif text-[17px] text-text-primary">
            <li class="flex gap-3"><span class="text-text-muted">—</span> Настроить сеть между несколькими серверами</li>
            <li class="flex gap-3"><span class="text-text-muted">—</span> Интегрировать сервисы и проверить их взаимодействие</li>
            <li class="flex gap-3"><span class="text-text-muted">—</span> Добавить новую точку без простоев сети</li>
            <li class="flex gap-3"><span class="text-text-muted">—</span> Получение сертификатов по сетям</li>
            <li class="flex gap-3"><span class="text-text-muted">—</span> Полное развертывания контейнеров</li>
            <li class="flex gap-3"><span class="text-text-muted">—</span> Настройка GPO</li>
            <li class="flex gap-3"><span class="text-text-muted">—</span> Настройка AD</li>
            <li class="flex gap-3"><span class="text-text-muted">—</span> Автоматизация рутинных действия</li>
          </ul>
        </div>
      </div>

      <!-- Add Goal Section -->
      <button class="border border-border-color bg-card-bg hover:bg-border-color transition-colors px-6 py-3 font-sans font-medium text-[15px] rounded-sm mb-4">
        Добавить цель
      </button>
      <p class="font-serif text-[15px] text-text-secondary leading-relaxed max-w-[350px]">
        Лучше всего две-три. После пяти это перестаёт быть инструментом прогресса и становится бюрократией.
      </p>
    </div>

    <BottomNav />
  </div>
</template>
