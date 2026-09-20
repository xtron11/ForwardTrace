<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue';
import { useAudioRecorder } from '../composables/useAudioRecorder';
import { useTimelineStore } from '../composables/useTimelineStore';

const props = defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'recorded', audioUrl: string): void;
}>();

const {
  isRecording,
  isPaused,
  duration,
  maxDuration,
  formattedTime,
  progressPercent,
  volumeLevel,
  waveformBars,
  recordedAudio,
  error,
  startRecording,
  pauseRecording,
  resumeRecording,
  stopRecording,
  cancelRecording,
} = useAudioRecorder();

const { addEntry } = useTimelineStore();

const isPlayingAudio = ref(false);
const audioElement = ref<HTMLAudioElement | null>(null);
const saveSuccess = ref(false);

watch(() => props.isOpen, (open) => {
  if (open) {
    saveSuccess.value = false;
    startRecording();
  } else {
    cancelRecording();
    stopAudioPlayback();
  }
});

const handleStop = () => {
  stopRecording();
};

const handlePauseToggle = () => {
  if (isPaused.value) {
    resumeRecording();
  } else {
    pauseRecording();
  }
};

const handleClose = () => {
  cancelRecording();
  stopAudioPlayback();
  emit('close');
};

const handleReRecord = () => {
  stopAudioPlayback();
  saveSuccess.value = false;
  startRecording();
};

const handleSaveToTimeline = () => {
  if (!recordedAudio.value) return;

  const now = new Date();
  const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
  const formattedDate = `${now.getDate()} ${months[now.getMonth()]}`;

  addEntry({
    date: formattedDate,
    duration: recordedAudio.value.duration || 1,
    audioUrl: recordedAudio.value.url,
    saidText: recordedAudio.value.transcription || '…записал мысли голосом за день.',
    extractedFact: recordedAudio.value.extractedFact || 'голосовая хроника дня',
    goalContext: 'Цель · довести задуманное до результата',
  });

  saveSuccess.value = true;
  emit('recorded', recordedAudio.value.url);

  setTimeout(() => {
    handleClose();
  }, 1200);
};

const toggleAudioPlayback = () => {
  if (!audioElement.value && recordedAudio.value?.url) {
    audioElement.value = new Audio(recordedAudio.value.url);
    audioElement.value.onended = () => {
      isPlayingAudio.value = false;
    };
  }

  if (audioElement.value) {
    if (isPlayingAudio.value) {
      audioElement.value.pause();
      isPlayingAudio.value = false;
    } else {
      audioElement.value.play();
      isPlayingAudio.value = true;
    }
  }
};

const stopAudioPlayback = () => {
  if (audioElement.value) {
    audioElement.value.pause();
    audioElement.value = null;
  }
  isPlayingAudio.value = false;
};

const downloadAudio = () => {
  if (!recordedAudio.value?.url) return;
  const a = document.createElement('a');
  a.href = recordedAudio.value.url;
  a.download = `forwardtrace-${Date.now()}.webm`;
  a.click();
};

onUnmounted(() => {
  stopAudioPlayback();
});
</script>

<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-[#0A1022]/85 backdrop-blur-md transition-all duration-300"
    role="dialog"
    aria-modal="true"
    aria-labelledby="record-modal-title"
  >
    <!-- Card Container -->
    <div
      class="relative w-full max-w-[540px] bg-[#111A30] border border-[#1F2B47] rounded-3xl p-6 sm:p-10 shadow-2xl shadow-black/60 text-[#E9EEF8] flex flex-col items-center text-center overflow-hidden"
    >
      <!-- Subtle ambient background glow -->
      <div
        class="absolute -top-32 -left-32 w-64 h-64 bg-[#8FB4FF]/10 rounded-full blur-3xl pointer-events-none"
      ></div>
      <div
        class="absolute -bottom-32 -right-32 w-64 h-64 bg-[#5B84E6]/10 rounded-full blur-3xl pointer-events-none"
      ></div>

      <!-- Close Button -->
      <button
        @click="handleClose"
        class="absolute top-6 right-6 text-[#8090A8] hover:text-[#E9EEF8] p-2 rounded-full hover:bg-[#16223C] transition-colors"
        aria-label="Закрыть"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>

      <!-- Header Label -->
      <div class="flex items-center gap-2 mb-3">
        <span
          class="w-2 h-2 rounded-full transition-all"
          :class="isRecording ? (isPaused ? 'bg-amber-400' : 'bg-[#FF5C5C] animate-pulse') : 'bg-[#8FB4FF]'"
        ></span>
        <span class="font-mono text-[11px] tracking-widest uppercase text-[#8090A8]">
          {{ isRecording ? (isPaused ? 'Запись на паузе' : 'Идёт запись') : (recordedAudio ? 'Запись готова' : 'Запись') }}
        </span>
      </div>

      <h3 id="record-modal-title" class="font-display text-xl sm:text-2xl font-semibold tracking-tight text-[#E9EEF8] mb-1">
        {{ isRecording ? (isPaused ? 'Пауза' : 'Слушаю') : (recordedAudio ? 'Прослушайте запись' : 'Микрофон') }}
      </h3>
      <p class="font-sans text-sm text-[#A5B2C9] mb-8">
        {{ isRecording ? '30 секунд · говорите свободно, можно сбивчиво' : (recordedAudio ? 'Вы можете сохранить эту запись в хронологию или перезаписать.' : 'Подключение микрофона...') }}
      </p>

      <!-- Error State -->
      <div v-if="error" class="w-full bg-[#3B1720] border border-[#7A2B3B] text-[#FFB8C2] rounded-2xl p-4 text-sm mb-6 text-left">
        <div class="font-semibold mb-1">Ошибка микрофона</div>
        <p class="text-xs leading-relaxed">{{ error }}</p>
        <button
          @click="startRecording"
          class="mt-3 text-xs font-mono uppercase tracking-wider text-white underline hover:no-underline"
        >
          Попробовать снова
        </button>
      </div>

      <!-- ACTIVE RECORDING STATE -->
      <div v-if="isRecording" class="w-full flex flex-col items-center">
        <!-- Pulsing Microphone / Visualizer Center -->
        <div class="relative flex items-center justify-center my-6">
          <!-- Animated ambient ripples based on volume level -->
          <div
            class="absolute w-36 h-36 rounded-full bg-[#8FB4FF]/20 transition-transform duration-100 ease-out"
            :style="{ transform: `scale(${1 + (volumeLevel / 100) * 0.4})` }"
          ></div>
          <div
            class="absolute w-48 h-48 rounded-full bg-[#8FB4FF]/10 transition-transform duration-150 ease-out"
            :style="{ transform: `scale(${1 + (volumeLevel / 100) * 0.7})` }"
          ></div>

          <!-- Central Circle Button -->
          <div
            class="relative z-10 w-28 h-28 rounded-full bg-[#16223C] border-2 border-[#8FB4FF] flex flex-col items-center justify-center shadow-lg shadow-[#8FB4FF]/20"
          >
            <!-- Microphone Icon -->
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#8FB4FF"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="transition-transform duration-100"
              :class="{ 'scale-110': volumeLevel > 30 }"
            >
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="22"></line>
            </svg>
            <span class="mt-1 font-mono text-[10px] uppercase tracking-wider text-[#A5B2C9]">
              {{ volumeLevel }}%
            </span>
          </div>
        </div>

        <!-- Real-time Equalizer Waveform Bars -->
        <div class="w-full max-w-xs h-14 flex items-center justify-between gap-1 px-4 my-4">
          <div
            v-for="(bar, index) in waveformBars"
            :key="index"
            class="flex-1 bg-[#8FB4FF] rounded-full transition-all duration-75"
            :style="{
              height: `${isPaused ? 8 : bar}%`,
              opacity: isPaused ? 0.3 : 0.6 + (bar / 100) * 0.4
            }"
          ></div>
        </div>

        <!-- Timer & Progress Bar -->
        <div class="w-full max-w-xs my-4">
          <div class="flex justify-between items-center font-mono text-xs text-[#8090A8] mb-2">
            <span class="text-[#E9EEF8] font-medium">{{ formattedTime }}</span>
            <span>00:{{ maxDuration }}</span>
          </div>
          <div class="w-full h-1.5 bg-[#1F2B47] rounded-full overflow-hidden">
            <div
              class="h-full bg-gradient-to-r from-[#5B84E6] to-[#8FB4FF] transition-all duration-300"
              :style="{ width: `${progressPercent}%` }"
            ></div>
          </div>
        </div>

        <!-- Recording Action Buttons -->
        <div class="flex items-center gap-4 mt-6">
          <button
            @click="handlePauseToggle"
            class="px-4 py-2.5 rounded-full border border-[#1F2B47] bg-[#16223C] text-xs font-mono tracking-wider uppercase text-[#A5B2C9] hover:text-[#E9EEF8] hover:border-[#32405F] transition-colors"
          >
            {{ isPaused ? 'Продолжить' : 'Пауза' }}
          </button>

          <button
            @click="handleStop"
            class="flex items-center gap-2 px-6 py-3 rounded-full bg-[#8FB4FF] text-[#0A1022] font-mono text-xs font-bold uppercase tracking-wider shadow-lg shadow-[#8FB4FF]/25 hover:bg-[#5B84E6] hover:text-[#FFFFFF] transition-all active:scale-95"
          >
            <div class="w-3 h-3 bg-[#0A1022] rounded-sm"></div>
            Завершить
          </button>

          <button
            @click="handleClose"
            class="px-4 py-2.5 rounded-full border border-[#1F2B47] text-xs font-mono tracking-wider uppercase text-[#8090A8] hover:text-[#E9EEF8] transition-colors"
          >
            Отмена
          </button>
        </div>
      </div>

      <!-- RECORDED / REVIEW STATE -->
      <div v-else-if="recordedAudio" class="w-full flex flex-col items-center">
        <!-- Audio Playback Card -->
        <div class="w-full bg-[#16223C] border border-[#1F2B47] rounded-2xl p-5 mb-6 text-left">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-3">
              <button
                @click="toggleAudioPlayback"
                class="w-12 h-12 rounded-full bg-[#8FB4FF] text-[#0A1022] flex items-center justify-center hover:bg-[#5B84E6] hover:text-white transition-all shadow-md"
                :title="isPlayingAudio ? 'Пауза' : 'Воспроизвести'"
              >
                <svg v-if="!isPlayingAudio" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="4" width="4" height="16"></rect>
                  <rect x="14" y="4" width="4" height="16"></rect>
                </svg>
              </button>
              <div>
                <p class="font-sans font-medium text-sm text-[#E9EEF8]">
                  {{ isPlayingAudio ? 'Воспроизведение...' : 'Голосовая запись' }}
                </p>
                <p class="font-mono text-xs text-[#8090A8]">
                  Длительность: {{ recordedAudio.duration }} сек
                </p>
              </div>
            </div>

            <!-- Download Button -->
            <button
              @click="downloadAudio"
              class="text-[#8090A8] hover:text-[#E9EEF8] p-2 rounded-lg hover:bg-[#111A30] transition-colors"
              title="Скачать файл"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
            </button>
          </div>

          <!-- Static Audio Waveform Graphic -->
          <div class="h-8 flex items-center gap-1 px-2 py-1 bg-[#111A30]/60 rounded-lg">
            <div
              v-for="n in 36"
              :key="n"
              class="flex-1 rounded-full"
              :class="isPlayingAudio ? 'bg-[#8FB4FF] animate-pulse' : 'bg-[#32405F]'"
              :style="{ height: `${Math.max(15, (Math.sin(n * 0.7) + 1.2) * 35)}%` }"
            ></div>
          </div>
        </div>

        <!-- Extracted Reflection Preview -->
        <div class="w-full bg-[#111A30] border-l-2 border-[#8FB4FF] pl-4 py-1 mb-8 text-left">
          <p class="font-mono text-[10px] tracking-widest uppercase text-[#8090A8] mb-1">
            Расшифровано · черновик
          </p>
          <p class="font-serif italic text-base text-[#A5B2C9] leading-relaxed">
            «…сегодня сел и записал мысли голосом, наконец-то чувствую движение вперед.»
          </p>
        </div>

        <!-- Success Toast -->
        <div v-if="saveSuccess" class="mb-4 text-emerald-400 font-mono text-xs uppercase tracking-wider flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 6 9 17l-5-5"></path>
          </svg>
          Запись сохранена в хронологию!
        </div>

        <!-- Actions -->
        <div class="flex flex-wrap items-center justify-center gap-3 w-full">
          <button
            @click="handleSaveToTimeline"
            :disabled="saveSuccess"
            class="flex-1 min-w-[180px] bg-[#8FB4FF] text-[#0A1022] font-mono text-xs font-bold uppercase tracking-wider py-3.5 px-6 rounded-full hover:bg-[#5B84E6] hover:text-[#FFFFFF] transition-all shadow-lg shadow-[#8FB4FF]/25 active:scale-95 disabled:opacity-50"
          >
            Сохранить в хронологию
          </button>

          <button
            @click="handleReRecord"
            class="border border-[#1F2B47] bg-[#16223C] text-[#A5B2C9] hover:text-[#E9EEF8] font-mono text-xs uppercase tracking-wider py-3.5 px-5 rounded-full hover:border-[#32405F] transition-colors"
          >
            Записать заново
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
