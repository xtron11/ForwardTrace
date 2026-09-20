<script setup lang="ts">
import { ref } from 'vue';

interface GoalItem {
  id: string;
  text: string;
  done: boolean;
}

interface Goal {
  id: string;
  title: string;
  purpose: string;
  isArchived: boolean;
  items: GoalItem[];
}

const goals = ref<Goal[]>([
  {
    id: 'goal-1',
    title: 'Развертывать вручную серверы и разные сервисы интегрировать внутрь. Научиться самостоятельно развертывать сети и настраивать сетевую инфраструктуру, а так же добавлять новые точки внутри сети',
    purpose: '«Для меня важно построить устойчивую и стабильную карьеру в сфере IT, по направлению инженера, системного администратора или информационная безопасность»',
    isArchived: false,
    items: [
      { id: '1', text: 'Настроить сеть между несколькими серверами', done: true },
      { id: '2', text: 'Интегрировать сервисы и проверить их взаимодействие', done: true },
      { id: '3', text: 'Добавить новую точку без простоев сети', done: false },
      { id: '4', text: 'Получение сертификатов по сетям', done: false },
      { id: '5', text: 'Полное развертывания контейнеров', done: false },
      { id: '6', text: 'Настройка GPO', done: false },
      { id: '7', text: 'Настройка AD', done: false },
      { id: '8', text: 'Автоматизация рутинных действия', done: false },
    ]
  }
]);

const isAddModalOpen = ref(false);
const newGoalTitle = ref('');
const newGoalPurpose = ref('');
const newGoalItemText = ref('');
const newGoalItems = ref<string[]>([]);

const addDraftItem = () => {
  if (newGoalItemText.value.trim()) {
    newGoalItems.value.push(newGoalItemText.value.trim());
    newGoalItemText.value = '';
  }
};

const removeDraftItem = (index: number) => {
  newGoalItems.value.splice(index, 1);
};

const handleSaveGoal = () => {
  if (!newGoalTitle.value.trim()) return;

  goals.value.push({
    id: `goal-${Date.now()}`,
    title: newGoalTitle.value.trim(),
    purpose: newGoalPurpose.value.trim() ? `«${newGoalPurpose.value.trim()}»` : '«Для меня важно довести начатое дело до устойчивого результата»',
    isArchived: false,
    items: newGoalItems.value.map((item, idx) => ({
      id: `${Date.now()}-${idx}`,
      text: item,
      done: false
    }))
  });

  newGoalTitle.value = '';
  newGoalPurpose.value = '';
  newGoalItems.value = [];
  isAddModalOpen.value = false;
};

const toggleItem = (goalId: string, itemId: string) => {
  const goal = goals.value.find(g => g.id === goalId);
  if (goal) {
    const item = goal.items.find(i => i.id === itemId);
    if (item) {
      item.done = !item.done;
    }
  }
};

const toggleArchive = (goalId: string) => {
  const goal = goals.value.find(g => g.id === goalId);
  if (goal) {
    goal.isArchived = !goal.isArchived;
  }
};
</script>

<template>
  <div class="w-full flex-1 flex flex-col justify-start px-6 py-8 md:py-12 max-w-[780px] mx-auto antialiased">
    
    <!-- Header -->
    <div class="mb-10 pb-6 border-b border-border-color">
      <p class="font-mono text-[11px] tracking-widest uppercase text-text-muted">
        Фокус и вектор · ForwardTrace
      </p>
      <h1 class="font-display font-semibold text-2xl sm:text-3xl text-text-primary mt-1">
        Над чем ты работаешь
      </h1>
      <p class="font-serif text-lg text-text-secondary mt-3 leading-relaxed">
        Одна запись покрывает все цели сразу. Расскажи, как прошёл день, и каждая часть попадёт к своей цели.
      </p>
    </div>

    <!-- Active Goals List -->
    <div class="space-y-8 mb-12">
      <article
        v-for="goal in goals.filter(g => !g.isArchived)"
        :key="goal.id"
        class="bg-card-bg border border-border-color rounded-3xl p-6 sm:p-9 transition-all hover:border-border-strong shadow-sm"
      >
        <!-- Top bar with actions -->
        <div class="flex flex-col sm:flex-row justify-between items-start gap-4 mb-6">
          <h2 class="text-xl sm:text-2xl font-sans font-medium leading-snug text-text-primary flex-1">
            {{ goal.title }}
          </h2>
          <div class="flex gap-4 font-mono text-[10px] tracking-widest uppercase text-text-muted shrink-0 pt-1">
            <button
              @click="toggleArchive(goal.id)"
              class="hover:text-accent transition-colors pb-0.5 border-b border-border-color hover:border-accent"
            >
              В архив
            </button>
          </div>
        </div>

        <!-- Purpose Quote -->
        <p class="font-serif italic text-base sm:text-lg text-text-secondary mb-8 leading-relaxed pl-4 border-l-2 border-accent/60 bg-card-surface/40 py-2 rounded-r-xl">
          {{ goal.purpose }}
        </p>

        <!-- Progress Definition Checklist -->
        <div class="border-t border-border-color pt-6">
          <div class="flex justify-between items-center mb-4">
            <p class="font-mono text-[10px] tracking-widest uppercase text-text-muted">
              Прогресс — это
            </p>
            <span class="font-mono text-[10px] text-accent">
              {{ goal.items.filter(i => i.done).length }} / {{ goal.items.length }} выполнено
            </span>
          </div>

          <ul class="space-y-2.5 font-serif text-[16px] text-text-primary">
            <li
              v-for="item in goal.items"
              :key="item.id"
              @click="toggleItem(goal.id, item.id)"
              class="flex items-start gap-3.5 cursor-pointer p-2 rounded-xl hover:bg-card-surface/60 transition-colors group"
            >
              <span
                class="w-4 h-4 rounded-md border mt-1 flex items-center justify-center shrink-0 transition-colors"
                :class="item.done ? 'bg-accent border-accent text-[#0A1022]' : 'border-border-color group-hover:border-accent'"
              >
                <svg v-if="item.done" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </span>
              <span :class="item.done ? 'line-through text-text-muted opacity-80' : 'text-text-primary'">
                {{ item.text }}
              </span>
            </li>
          </ul>
        </div>
      </article>
    </div>

    <!-- Add Goal Section -->
    <div class="pt-2 pb-8">
      <button
        v-if="!isAddModalOpen"
        @click="isAddModalOpen = true"
        class="border border-border-color bg-card-surface hover:bg-border-color hover:border-accent transition-all px-6 py-3 font-sans font-medium text-[14px] rounded-xl mb-4 text-text-primary flex items-center gap-2 shadow-sm"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
        Добавить цель
      </button>

      <!-- Add Goal Form Card -->
      <div
        v-else
        class="bg-card-bg border border-accent/40 rounded-3xl p-6 sm:p-8 shadow-xl mb-6"
      >
        <h3 class="font-display font-semibold text-lg text-text-primary mb-4">
          Новая цель
        </h3>

        <div class="space-y-4">
          <div>
            <label class="block font-mono text-[10px] uppercase tracking-wider text-text-muted mb-1.5">
              Формулировка цели
            </label>
            <input
              v-model="newGoalTitle"
              type="text"
              placeholder="Например: Научиться самостоятельно настраивать инфраструктуру"
              class="w-full bg-card-surface border border-border-color rounded-xl px-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent font-sans"
            />
          </div>

          <div>
            <label class="block font-mono text-[10px] uppercase tracking-wider text-text-muted mb-1.5">
              Ради чего это важно (ваша личная мотивация)
            </label>
            <textarea
              v-model="newGoalPurpose"
              rows="2"
              placeholder="Для меня важно..."
              class="w-full bg-card-surface border border-border-color rounded-xl px-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent font-sans resize-none"
            ></textarea>
          </div>

          <div>
            <label class="block font-mono text-[10px] uppercase tracking-wider text-text-muted mb-1.5">
              Критерии прогресса («Прогресс — это:»)
            </label>
            <div class="flex gap-2 mb-2">
              <input
                v-model="newGoalItemText"
                @keyup.enter="addDraftItem"
                type="text"
                placeholder="Добавить конкретный шаг или маркер"
                class="flex-1 bg-card-surface border border-border-color rounded-xl px-4 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent font-sans"
              />
              <button
                @click="addDraftItem"
                class="px-4 py-2 rounded-xl bg-card-surface border border-border-color font-mono text-xs uppercase hover:border-accent text-text-primary"
              >
                +
              </button>
            </div>

            <ul v-if="newGoalItems.length > 0" class="space-y-1.5 mt-2">
              <li
                v-for="(it, idx) in newGoalItems"
                :key="idx"
                class="flex items-center justify-between text-xs font-serif bg-card-surface px-3 py-1.5 rounded-lg border border-border-color text-text-primary"
              >
                <span>— {{ it }}</span>
                <button @click="removeDraftItem(idx)" class="text-text-muted hover:text-red-400 font-mono">×</button>
              </li>
            </ul>
          </div>

          <div class="flex justify-end gap-3 pt-4 border-t border-border-color">
            <button
              @click="isAddModalOpen = false"
              class="px-4 py-2 rounded-xl text-xs font-mono text-text-muted hover:text-text-primary"
            >
              Отмена
            </button>
            <button
              @click="handleSaveGoal"
              class="px-5 py-2 rounded-xl bg-accent text-[#0A1022] text-xs font-mono font-bold uppercase tracking-wider hover:bg-accent-hover hover:text-white transition-colors"
            >
              Сохранить цель
            </button>
          </div>
        </div>
      </div>

      <p class="font-serif text-[14px] text-text-secondary leading-relaxed max-w-[420px]">
        Лучше всего две-три. После пяти это перестаёт быть инструментом прогресса и становится бюрократией.
      </p>
    </div>

  </div>
</template>
