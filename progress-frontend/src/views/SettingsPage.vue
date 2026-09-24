<script setup lang="ts">
import { computed, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { usePWAInstall } from '../usePWAInstall';

const router = useRouter();
const { deferredPrompt, isInstalled, isIOS, install } = usePWAInstall();

const goBack = () => {
  if (window.history.length > 2) {
    router.back();
  } else {
    router.push('/today');
  }
};

const isInstallable = computed(() => !!deferredPrompt.value);
const showIOSGuide = ref(false);
const showDesktopTip = ref(false);

// Notification API logic
const notificationsSupported = ref(typeof window !== 'undefined' && 'Notification' in window);
const notificationPermission = ref<NotificationPermission>('default');
const reminderTime = ref('21:00');
const testSuccessMsg = ref('');

const checkNotificationPermission = () => {
  if (notificationsSupported.value) {
    notificationPermission.value = Notification.permission;
  }
  const savedTime = localStorage.getItem('forwardtrace_reminder_time');
  if (savedTime) reminderTime.value = savedTime;
};

onMounted(() => {
  checkNotificationPermission();
});

const requestNotification = async () => {
  if (!notificationsSupported.value) return;
  try {
    const permission = await Notification.requestPermission();
    notificationPermission.value = permission;
    if (permission === 'granted') {
      localStorage.setItem('forwardtrace_reminder_enabled', 'true');
      localStorage.setItem('forwardtrace_reminder_time', reminderTime.value);
      sendTestNotification();
    }
  } catch (err) {
    console.error('Notification permission error:', err);
  }
};

const saveReminderTime = () => {
  localStorage.setItem('forwardtrace_reminder_time', reminderTime.value);
  testSuccessMsg.value = `Время напоминания сохранено: ${reminderTime.value}`;
  setTimeout(() => { testSuccessMsg.value = ''; }, 3000);
};

const sendTestNotification = () => {
  if (notificationPermission.value !== 'granted') return;
  try {
    new Notification('ForwardTrace', {
      body: 'Время зафиксировать мысли и прогресс за день.',
      icon: '/pwa-192x192.png',
    });
    testSuccessMsg.value = 'Тестовое уведомление отправлено!';
    setTimeout(() => { testSuccessMsg.value = ''; }, 4000);
  } catch (e) {
    console.warn('Direct Notification failed, trying ServiceWorker:', e);
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.ready.then((reg) => {
        reg.showNotification('ForwardTrace', {
          body: 'Время зафиксировать мысли и прогресс за день.',
          icon: '/pwa-192x192.png',
        });
        testSuccessMsg.value = 'Тестовое уведомление отправлено!';
        setTimeout(() => { testSuccessMsg.value = ''; }, 4000);
      });
    }
  }
};

const disableNotifications = () => {
  localStorage.removeItem('forwardtrace_reminder_enabled');
  testSuccessMsg.value = 'Напоминания отключены в приложении';
  setTimeout(() => { testSuccessMsg.value = ''; }, 3000);
};

const handleLogout = () => {
  router.push('/');
};
</script>

<template>
  <div class="min-h-screen bg-bg-primary text-text-primary font-sans relative">
    
    <!-- Top bar -->
    <div class="flex justify-between items-center px-6 py-8">
      <span class="font-mono text-[11px] tracking-widest uppercase text-text-muted">НАСТРОЙКИ</span>
      <button @click="goBack" class="font-mono text-[11px] tracking-widest uppercase text-text-muted hover:text-text-primary transition-colors">
        ЗАКРЫТЬ
      </button>
    </div>

    <div class="max-w-[520px] mx-auto px-6 pt-6 pb-20">
      
      <!-- Profile Section -->
      <div class="flex items-center gap-6 mb-12">
        <div class="w-12 h-12 flex items-center justify-center shrink-0">
          <svg viewBox="0 0 100 100" fill="none" class="w-full h-full text-text-primary">
            <path d="M20 50h40" stroke="currentColor" stroke-width="13" stroke-linecap="square"></path>
            <path d="M40 82 96 26" stroke="currentColor" stroke-width="13" stroke-linecap="square" class="text-accent"></path>
            <path d="M68 24h30v30" stroke="currentColor" stroke-width="13" stroke-linecap="square"></path>
          </svg>
        </div>
        <div>
          <h2 class="text-2xl font-sans font-medium mb-1 text-text-primary">Tester</h2>
          <p class="font-mono text-[11px] text-text-muted">tester@mail.ru</p>
          <p class="font-mono text-[11px] uppercase tracking-widest text-text-muted mt-2">С НАМИ С 6 СЕНТЯБРЯ</p>
        </div>
      </div>

      <div class="space-y-10">
        <!-- App Install Block -->
        <div class="flex flex-col sm:flex-row gap-4 sm:gap-12 border-t border-border-color pt-8">
          <h3 class="font-mono text-[11px] tracking-widest uppercase text-text-muted shrink-0 sm:w-32">ПРИЛОЖЕНИЕ</h3>
          <div class="flex-1">
            <p class="font-serif text-base text-text-secondary mb-5 leading-relaxed">
              Добавь на домашний экран — открывается в полноэкранном режиме без браузера и работает без сети.
            </p>
            
            <template v-if="!isInstalled">
              <!-- If native Chrome / Android install prompt is ready -->
              <div v-if="isInstallable" class="space-y-3">
                <button 
                  @click="install"
                  class="w-full border-2 border-accent bg-accent/10 py-3.5 px-4 font-mono text-[12px] tracking-wider uppercase text-accent font-semibold hover:bg-accent hover:text-white transition-colors rounded-xl flex items-center justify-center gap-2"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  УСТАНОВИТЬ ПРИЛОЖЕНИЕ
                </button>
              </div>

              <!-- iOS Safari flow -->
              <div v-else-if="isIOS" class="space-y-3">
                <button 
                  @click="showIOSGuide = !showIOSGuide"
                  class="w-full border border-border-color py-3 px-4 font-mono text-[11px] tracking-widest uppercase text-text-primary hover:bg-card-bg transition-colors rounded-xl flex items-center justify-center gap-2"
                >
                  УСТАНОВИТЬ НА IPHONE / IPAD
                </button>
                <div v-if="showIOSGuide" class="p-4 border border-border-color bg-card-bg/60 text-xs text-text-secondary rounded-xl space-y-2">
                  <p>1. Внизу экрана в браузере Safari нажмите иконку <strong>«Поделиться»</strong> (квадрат со стрелкой вверх).</p>
                  <p>2. Прокрутите список вниз и нажмите <strong>«На экран „Домой“»</strong>.</p>
                  <p>3. Нажмите <strong>«Добавить»</strong> — ForwardTrace появится на рабочем столе телефона как нативное приложение.</p>
                </div>
              </div>

              <!-- Desktop Chrome / Edge / Fallback -->
              <div v-else class="space-y-3">
                <button
                  @click="showDesktopTip = !showDesktopTip"
                  class="w-full border border-border-color py-3 px-4 font-mono text-[11px] tracking-widest uppercase text-text-primary hover:bg-card-bg transition-colors rounded-xl flex items-center justify-center gap-2"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  КАК УСТАНОВИТЬ В БРАУЗЕРЕ
                </button>

                <div v-if="showDesktopTip" class="p-4 border border-border-color bg-card-bg/60 text-xs text-text-secondary rounded-xl space-y-2">
                  <p>• <strong>В Chrome / Edge (ПК)</strong>: нажмите иконку монитора со стрелкой ⤓ в правом конце адресной строки или в меню браузера (три точки ⋮) выберите <em>«Установить приложение ForwardTrace»</em>.</p>
                  <p>• <strong>На Android (Chrome)</strong>: нажмите три точки ⋮ в правом верхнем углу браузера ➔ <em>«Установить приложение»</em> или <em>«Добавить на главный экран»</em>.</p>
                </div>
              </div>
            </template>

            <!-- Already installed badge -->
            <div v-else class="flex items-center gap-2 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-xs font-mono">
              <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              <span>ПРИЛОЖЕНИЕ УСТАНОВЛЕНО И РАБОТАЕТ АВТОНОМНО</span>
            </div>
          </div>
        </div>

        <!-- Notifications Block -->
        <div class="flex flex-col sm:flex-row gap-4 sm:gap-12 border-t border-border-color pt-8">
          <h3 class="font-mono text-[11px] tracking-widest uppercase text-text-muted shrink-0 sm:w-32">НАПОМИНАНИЯ</h3>
          <div class="flex-1 space-y-4">
            
            <!-- Notifications Granted -->
            <template v-if="notificationPermission === 'granted'">
              <p class="font-serif text-base text-text-secondary leading-relaxed">
                Включены. Будем напоминать зафиксировать день.
              </p>

              <div class="flex items-center gap-3">
                <label class="font-mono text-xs text-text-muted uppercase tracking-wider">Время:</label>
                <input 
                  type="time" 
                  v-model="reminderTime" 
                  @change="saveReminderTime"
                  class="bg-card-bg border border-border-color px-3 py-1.5 rounded-lg text-sm font-mono text-text-primary focus:outline-none focus:border-accent"
                />
              </div>

              <div class="flex flex-col sm:flex-row gap-2 pt-1">
                <button 
                  @click="sendTestNotification"
                  class="border border-border-color py-2.5 px-4 font-mono text-[11px] tracking-wider uppercase text-text-primary hover:bg-card-bg transition-colors rounded-xl flex-1 text-center"
                >
                  ПРОВЕРИТЬ УВЕДОМЛЕНИЕ
                </button>
                <button 
                  @click="disableNotifications"
                  class="border border-border-color/50 py-2.5 px-3 font-mono text-[11px] tracking-wider uppercase text-text-muted hover:text-rose-400 hover:border-rose-400/40 transition-colors rounded-xl text-center"
                >
                  ОТКЛЮЧИТЬ
                </button>
              </div>
            </template>

            <!-- Notifications Blocked in Browser -->
            <template v-else-if="notificationPermission === 'denied'">
              <p class="font-serif text-base text-rose-400/90 leading-relaxed">
                Уведомления заблокированы в настройках браузера.
              </p>
              <p class="text-xs text-text-muted leading-relaxed">
                Чтобы включить: нажмите на значок настроек сайта (или замочек) слева от адресной строки браузера и разрешите «Уведомления».
              </p>
            </template>

            <!-- Notifications Default / Off -->
            <template v-else>
              <p class="font-serif text-base text-text-secondary leading-relaxed">
                Выключены. Придётся помнить самому.
              </p>
              <button 
                @click="requestNotification"
                class="w-full border border-border-color py-3.5 px-4 font-mono text-[11px] tracking-widest uppercase text-text-primary hover:bg-card-bg transition-colors rounded-xl"
              >
                ВКЛЮЧИТЬ НАПОМИНАНИЯ
              </button>
            </template>

            <!-- Feedback Toast / Status -->
            <div v-if="testSuccessMsg" class="p-2.5 rounded-lg bg-accent/10 border border-accent/30 text-accent font-mono text-xs text-center animate-fade-in">
              {{ testSuccessMsg }}
            </div>
          </div>
        </div>

        <!-- Version Block -->
        <div class="flex flex-col sm:flex-row gap-4 sm:gap-12 border-t border-border-color py-8">
          <h3 class="font-mono text-[11px] tracking-widest uppercase text-text-muted shrink-0 sm:w-32">ВЕРСИЯ</h3>
          <div class="flex-1">
            <p class="font-mono text-[13px] text-text-secondary">
              0.1.0 · PWA Ready
            </p>
          </div>
        </div>

        <!-- Logout Block -->
        <div class="border-t border-border-color pt-8 pb-12">
          <button @click="handleLogout" class="font-mono text-[11px] tracking-widest uppercase text-text-muted hover:text-text-primary transition-colors">
            ВЫЙТИ
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
