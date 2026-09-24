<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useTheme } from '../composables/useTheme';
import { useTimelineStore } from '../composables/useTimelineStore';

const props = defineProps<{
  collapsed?: boolean;
}>();

const emit = defineEmits<{
  (e: 'open-record'): void;
  (e: 'navigate'): void;
}>();

const route = useRoute();
const router = useRouter();
const { isDark, toggleDark } = useTheme();
const { totalDays, entries } = useTimelineStore();

const navItems = [
  {
    path: '/today',
    name: 'today',
    label: 'Сегодня',
    sublabel: 'Запись дня',
    icon: 'today'
  },
  {
    path: '/timeline',
    name: 'timeline',
    label: 'Хроника',
    sublabel: 'Лента записей',
    badge: computed(() => entries.value.length),
    icon: 'timeline'
  },
  {
    path: '/report',
    name: 'report',
    label: 'Отчёт',
    sublabel: 'Срезы и анализ',
    icon: 'report'
  },
  {
    path: '/goals',
    name: 'goals',
    label: 'Цели',
    sublabel: 'Фокус движения',
    icon: 'goals'
  }
];

const isActive = (path: string) => {
  return route.path === path;
};

const handleNavClick = (path: string) => {
  router.push(path);
  emit('navigate');
};

const triggerRecord = () => {
  emit('open-record');
};
</script>

<template>
  <aside
    class="flex flex-col justify-between h-full bg-card-bg border-r border-border-color select-none text-text-primary transition-colors"
    :class="collapsed ? 'w-20' : 'w-64 lg:w-72'"
  >
    <!-- Top Brand & Header -->
    <div>
      <!-- Brand Logo / Header -->
      <div class="px-5 py-6 border-b border-border-color flex items-center justify-between">
        <router-link
          to="/"
          @click="emit('navigate')"
          class="flex items-center gap-3 text-text-primary hover:text-accent transition-colors group"
          title="На главную"
        >
          <!-- Signature Forward Trace Wave Mark -->
          <div class="w-9 h-9 rounded-xl bg-card-surface border border-border-color flex items-center justify-center text-accent group-hover:border-accent transition-colors shadow-sm">
            <svg width="20" height="20" viewBox="0 0 18 18" aria-hidden="true" focusable="false">
              <path d="M2 13.5 C5.5 13.5 5.5 4.5 9 4.5 C12.5 4.5 12.5 9 16 9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              <circle cx="16" cy="9" r="2.2" fill="currentColor"/>
            </svg>
          </div>

          <div v-if="!collapsed" class="flex flex-col">
            <span class="font-display font-bold text-[16px] tracking-tight text-text-primary group-hover:text-accent transition-colors">
              ForwardTrace
            </span>
            <span class="font-mono text-[10px] tracking-wider text-text-muted uppercase">
              Хроника пути
            </span>
          </div>
        </router-link>
      </div>

      <!-- Quick Record Call-To-Action Button in Sidebar -->
      <div class="p-4">
        <button
          @click="triggerRecord"
          class="w-full relative group flex items-center justify-center gap-2.5 py-3 rounded-2xl bg-accent text-[#0A1022] font-mono text-xs font-bold uppercase tracking-wider shadow-lg shadow-accent/15 hover:bg-accent-hover hover:text-[#FFFFFF] transition-all active:scale-[0.98]"
          :class="collapsed ? 'px-0' : 'px-4'"
          title="Записать мысль голосом"
        >
          <span class="relative flex h-2.5 w-2.5">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#0A1022] opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#0A1022] group-hover:bg-[#FFFFFF]"></span>
          </span>
          <span v-if="!collapsed">Записать голос</span>
        </button>
      </div>

      <!-- Navigation Links -->
      <nav class="px-3 space-y-1.5 mt-1" aria-label="Основная навигация">
        <button
          v-for="item in navItems"
          :key="item.path"
          @click="handleNavClick(item.path)"
          class="w-full flex items-center gap-3.5 px-3.5 py-3 rounded-xl font-sans text-sm transition-all text-left relative group"
          :class="isActive(item.path)
            ? 'bg-card-surface text-text-primary font-medium border border-border-strong shadow-sm'
            : 'text-text-secondary hover:text-text-primary hover:bg-card-surface/50 border border-transparent'"
        >
          <!-- Active Bar Accent on Left -->
          <div
            v-if="isActive(item.path)"
            class="absolute left-1 top-2.5 bottom-2.5 w-1 bg-accent rounded-full"
          ></div>

          <!-- Icon -->
          <div
            class="w-6 h-6 flex items-center justify-center shrink-0 transition-colors"
            :class="isActive(item.path) ? 'text-accent' : 'text-text-muted group-hover:text-text-primary'"
          >
            <!-- Today Icon -->
            <svg v-if="item.icon === 'today'" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect width="18" height="18" x="3" y="4" rx="2" ry="2"/>
              <line x1="16" x2="16" y1="2" y2="6"/>
              <line x1="8" x2="8" y1="2" y2="6"/>
              <line x1="3" x2="21" y1="10" y2="10"/>
              <circle cx="12" cy="16" r="1.5" fill="currentColor"/>
            </svg>

            <!-- Timeline Icon -->
            <svg v-else-if="item.icon === 'timeline'" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" x2="12" y1="2" y2="22"/>
              <polyline points="18 12 12 18 6 12"/>
              <circle cx="12" cy="6" r="2" fill="currentColor"/>
            </svg>

            <!-- Report Icon -->
            <svg v-else-if="item.icon === 'report'" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" x2="8" y1="13" y2="13"/>
              <line x1="16" x2="8" y1="17" y2="17"/>
              <line x1="10" x2="8" y1="9" y2="9"/>
            </svg>

            <!-- Goals Icon -->
            <svg v-else-if="item.icon === 'goals'" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <circle cx="12" cy="12" r="6"/>
              <circle cx="12" cy="12" r="2" fill="currentColor"/>
            </svg>
          </div>

          <!-- Label & Sublabel -->
          <div v-if="!collapsed" class="flex-1 min-w-0 flex items-center justify-between">
            <div class="truncate">
              <span class="block font-medium tracking-tight text-[14px]">
                {{ item.label }}
              </span>
              <span class="block text-[11px] font-mono text-text-muted truncate">
                {{ item.sublabel }}
              </span>
            </div>

            <!-- Optional Badge -->
            <span
              v-if="item.badge && item.badge.value > 0"
              class="ml-2 px-2 py-0.5 rounded-full text-[10px] font-mono bg-card-bg border border-border-color text-text-muted"
            >
              {{ item.badge.value }}
            </span>
          </div>
        </button>
      </nav>

      <!-- Mini Journey Stat Badge -->
      <div v-if="!collapsed" class="mx-4 mt-6 p-3.5 rounded-2xl bg-card-surface border border-border-color">
        <div class="flex items-center justify-between font-mono text-[10px] text-text-muted uppercase mb-1.5">
          <span>В пути</span>
          <span class="text-accent font-bold">{{ totalDays }} дней</span>
        </div>
        <div class="w-full h-1 bg-border-color rounded-full overflow-hidden">
          <div
            class="h-full bg-accent transition-all duration-500 rounded-full"
            :style="{ width: `${Math.min(100, Math.max(8, (totalDays / 14) * 100))}%` }"
          ></div>
        </div>
      </div>
    </div>

    <!-- Bottom Actions & User Tools -->
    <div class="p-4 border-t border-border-color space-y-2">
      <!-- Settings -->
      <router-link
        to="/settings"
        @click="emit('navigate')"
        class="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl font-sans text-sm text-text-secondary hover:text-text-primary hover:bg-card-surface transition-all"
        :class="{ 'bg-card-surface text-text-primary': route.path === '/settings' }"
        title="Настройки аккаунта"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="text-text-muted shrink-0">
          <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
          <circle cx="12" cy="12" r="3"/>
        </svg>
        <span v-if="!collapsed" class="font-medium text-[13px]">Настройки</span>
      </router-link>

      <!-- Theme Toggle Button -->
      <button
        @click="toggleDark"
        class="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl font-sans text-sm text-text-secondary hover:text-text-primary hover:bg-card-surface transition-all"
        title="Сменить тему оформления"
      >
        <div class="flex items-center gap-3">
          <svg v-if="!isDark" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="text-text-muted shrink-0">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="text-accent shrink-0">
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
          <span v-if="!collapsed" class="font-medium text-[13px]">{{ isDark ? 'Тёмная тема' : 'Светлая тема' }}</span>
        </div>
        <span v-if="!collapsed" class="font-mono text-[10px] text-text-muted uppercase">
          {{ isDark ? 'DARK' : 'LIGHT' }}
        </span>
      </button>

      <!-- Back to Landing Link -->
      <router-link
        to="/"
        class="w-full flex items-center gap-3 px-3.5 py-2 rounded-xl font-mono text-[11px] text-text-muted hover:text-text-primary transition-colors uppercase tracking-wider"
        title="О проекте"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="19" y1="12" x2="5" y2="12"></line>
          <polyline points="12 19 5 12 12 5"></polyline>
        </svg>
        <span v-if="!collapsed">О ForwardTrace</span>
      </router-link>
    </div>
  </aside>
</template>
