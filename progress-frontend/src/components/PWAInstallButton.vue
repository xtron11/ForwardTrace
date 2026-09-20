<script setup lang="ts">
import { ref, computed } from 'vue';
import { usePWAInstall } from '../usePWAInstall';

const { deferredPrompt, isInstalled, isIOS, install } = usePWAInstall();
const showIOSGuide = ref(false);

const isInstallable = computed(() => !!deferredPrompt.value);
</script>

<template>
  <!-- If already running as an installed PWA, hide the button -->
  <template v-if="!isInstalled">
    <!-- Chromium / Android / Desktop flow -->
    <button
      v-if="isInstallable"
      @click="install"
      class="flex items-center gap-2 rounded-xl bg-card-bg px-4 py-2 text-sm font-bold text-text-primary border border-border-color shadow-sm hover:bg-border-color transition"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      Установить приложение
    </button>

    <!-- iOS Safari flow -->
    <template v-else-if="isIOS">
      <button
        @click="showIOSGuide = true"
        class="flex items-center gap-2 rounded-xl bg-card-bg border border-border-color px-3 py-1.5 text-xs font-bold text-text-secondary shadow-sm hover:bg-border-color transition"
      >
        Установить на iOS
      </button>

      <div v-if="showIOSGuide" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div class="w-full max-w-sm rounded-2xl bg-card-bg p-6 shadow-xl border border-border-color">
          <h3 class="text-lg font-semibold text-text-primary">Установить на iPhone / iPad</h3>
          <p class="mt-2 text-sm text-text-secondary">
            1. Нажмите кнопку <strong>Поделиться</strong> в панели Safari.<br />
            2. Прокрутите вниз и нажмите <strong>На экран «Домой»</strong>.
          </p>
          <button
            @click="showIOSGuide = false"
            class="mt-4 w-full rounded-xl bg-accent py-2 text-sm font-bold text-[#FFFFFF] shadow-sm hover:bg-accent-hover transition"
          >
            Закрыть
          </button>
        </div>
      </div>
    </template>
  </template>
</template>
