<script setup lang="ts">
import { ref } from 'vue';
import { useRoute } from 'vue-router';
import NavigationSidebar from '../components/NavigationSidebar.vue';
import AudioRecordingModal from '../components/AudioRecordingModal.vue';
import { useTheme } from '../composables/useTheme';
import { useTimelineStore } from '../composables/useTimelineStore';

const route = useRoute();
const { isDark, toggleDark } = useTheme();
const { totalDays } = useTimelineStore();

const isRecordModalOpen = ref(false);

const openRecordModal = () => {
  isRecordModalOpen.value = true;
};

const closeRecordModal = () => {
  isRecordModalOpen.value = false;
};
</script>

<template>
  <div class="min-h-screen bg-bg-primary text-text-primary flex flex-col md:flex-row antialiased selection:bg-accent selection:text-[#0A1022]">
    <!-- Shared Voice Recording Modal (Available to all core views) -->
    <AudioRecordingModal
      :is-open="isRecordModalOpen"
      @close="closeRecordModal"
    />

    <!-- Desktop & Tablet Shared Navigation Sidebar -->
    <div class="hidden md:block sticky top-0 h-screen z-30 shrink-0">
      <NavigationSidebar
        @open-record="openRecordModal"
      />
    </div>

    <!-- Mobile Top Navigation Header (Only visible on small screens) -->
    <header class="md:hidden sticky top-0 z-40 w-full bg-card-bg/95 border-b border-border-color backdrop-blur-md px-4 py-3 flex items-center justify-between">
      <router-link to="/" class="flex items-center gap-2.5 text-text-primary">
        <div class="w-7 h-7 rounded-lg bg-card-surface border border-border-color flex items-center justify-center text-accent">
          <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true" focusable="false">
            <path d="M2 13.5 C5.5 13.5 5.5 4.5 9 4.5 C12.5 4.5 12.5 9 16 9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            <circle cx="16" cy="9" r="2" fill="currentColor"/>
          </svg>
        </div>
        <span class="font-display font-bold text-sm tracking-tight">ForwardTrace</span>
      </router-link>

      <div class="flex items-center gap-1.5">
        <!-- Theme Toggle -->
        <button
          @click="toggleDark"
          class="p-2 rounded-xl text-text-muted hover:text-text-primary hover:bg-card-surface transition-colors"
          aria-label="Сменить тему"
        >
          <svg v-if="!isDark" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"></circle>
            <line x1="12" y1="1" x2="12" y2="3"></line>
            <line x1="12" y1="21" x2="12" y2="23"></line>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
            <line x1="1" y1="12" x2="3" y2="12"></line>
            <line x1="21" y1="12" x2="23" y2="12"></line>
          </svg>
        </button>

        <!-- Settings Link for Mobile -->
        <router-link
          to="/settings"
          id="mobile-settings-btn"
          class="p-2 rounded-xl text-text-muted hover:text-text-primary hover:bg-card-surface transition-colors"
          :class="{ 'bg-card-surface text-accent': route.path === '/settings' }"
          aria-label="Настройки"
          title="Настройки"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        </router-link>
      </div>
    </header>

    <!-- Main Content Stage (Switches core views smoothly) -->
    <main class="flex-1 min-w-0 min-h-screen relative flex flex-col pb-20 md:pb-6">
      <router-view v-slot="{ Component }">
        <transition name="fade-view" mode="out-in">
          <component
            :is="Component"
            @open-record="openRecordModal"
          />
        </transition>
      </router-view>
    </main>

    <!-- Mobile Persistent Bottom Navigation Bar -->
    <nav class="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-card-bg/95 border-t border-border-color backdrop-blur-lg flex items-center justify-around py-2 px-2 shadow-lg">
      <router-link
        to="/today"
        class="flex flex-col items-center py-1 px-3 text-[10px] font-mono uppercase tracking-wider transition-colors"
        :class="route.path === '/today' ? 'text-accent font-bold' : 'text-text-muted hover:text-text-primary'"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="mb-1">
          <rect width="18" height="18" x="3" y="4" rx="2" ry="2"/>
          <line x1="16" x2="16" y1="2" y2="6"/>
          <line x1="8" x2="8" y1="2" y2="6"/>
          <line x1="3" x2="21" y1="10" y2="10"/>
        </svg>
        <span>Сегодня</span>
      </router-link>

      <router-link
        to="/timeline"
        class="flex flex-col items-center py-1 px-3 text-[10px] font-mono uppercase tracking-wider transition-colors"
        :class="route.path === '/timeline' ? 'text-accent font-bold' : 'text-text-muted hover:text-text-primary'"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="mb-1">
          <line x1="12" x2="12" y1="2" y2="22"/>
          <polyline points="18 12 12 18 6 12"/>
        </svg>
        <span>Хроника</span>
      </router-link>

      <!-- Center Voice Bubble Button -->
      <button
        @click="openRecordModal"
        class="w-11 h-11 -mt-4 rounded-full bg-accent text-[#0A1022] flex items-center justify-center shadow-lg shadow-accent/30 active:scale-95 transition-transform"
        aria-label="Записать"
      >
        <div class="w-3 h-3 rounded-full bg-[#0A1022]"></div>
      </button>

      <router-link
        to="/report"
        class="flex flex-col items-center py-1 px-3 text-[10px] font-mono uppercase tracking-wider transition-colors"
        :class="route.path === '/report' ? 'text-accent font-bold' : 'text-text-muted hover:text-text-primary'"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="mb-1">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
        <span>Отчёт</span>
      </router-link>

      <router-link
        to="/goals"
        class="flex flex-col items-center py-1 px-3 text-[10px] font-mono uppercase tracking-wider transition-colors"
        :class="route.path === '/goals' ? 'text-accent font-bold' : 'text-text-muted hover:text-text-primary'"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="mb-1">
          <circle cx="12" cy="12" r="10"/>
          <circle cx="12" cy="12" r="2" fill="currentColor"/>
        </svg>
        <span>Цели</span>
      </router-link>
    </nav>
  </div>
</template>

<style scoped>
.fade-view-enter-active,
.fade-view-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.fade-view-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.fade-view-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
