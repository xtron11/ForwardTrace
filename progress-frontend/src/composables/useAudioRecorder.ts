import { ref, computed, onUnmounted } from 'vue';

export interface RecordedAudio {
  id: string;
  blob: Blob;
  url: string;
  duration: number; // in seconds
  createdAt: string;
  transcription?: string;
  extractedFact?: string;
}

export function useAudioRecorder() {
  const isRecording = ref(false);
  const isPaused = ref(false);
  const duration = ref(0);
  const maxDuration = 30; // 30 seconds limit
  const error = ref<string | null>(null);
  const volumeLevel = ref(0); // 0 to 100
  const waveformBars = ref<number[]>(new Array(24).fill(10));
  
  const recordedAudio = ref<RecordedAudio | null>(null);

  let mediaStream: MediaStream | null = null;
  let mediaRecorder: MediaRecorder | null = null;
  let audioChunks: Blob[] = [];
  let timerInterval: number | null = null;
  
  let audioContext: AudioContext | null = null;
  let analyser: AnalyserNode | null = null;
  let sourceNode: MediaStreamAudioSourceNode | null = null;
  let animationFrameId: number | null = null;

  const formattedTime = computed(() => {
    const mins = Math.floor(duration.value / 60).toString().padStart(2, '0');
    const secs = (duration.value % 60).toString().padStart(2, '0');
    return `${mins}:${secs}`;
  });

  const progressPercent = computed(() => {
    return Math.min(100, Math.round((duration.value / maxDuration) * 100));
  });

  const analyzeAudio = () => {
    if (!analyser || !isRecording.value || isPaused.value) return;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteFrequencyData(dataArray);

    // Calculate overall volume level
    let sum = 0;
    for (let i = 0; i < bufferLength; i++) {
      sum += dataArray[i];
    }
    const average = sum / bufferLength;
    volumeLevel.value = Math.min(100, Math.round((average / 128) * 100));

    // Downsample to 24 bars for visualizer
    const barsCount = 24;
    const step = Math.floor(bufferLength / barsCount);
    const newBars: number[] = [];

    for (let i = 0; i < barsCount; i++) {
      let barSum = 0;
      for (let j = 0; j < step; j++) {
        barSum += dataArray[i * step + j] || 0;
      }
      const barAvg = barSum / step;
      // normalize between 12% and 100%
      const barHeight = Math.max(12, Math.round((barAvg / 255) * 100));
      newBars.push(barHeight);
    }

    waveformBars.value = newBars;
    animationFrameId = requestAnimationFrame(analyzeAudio);
  };

  const startRecording = async () => {
    error.value = null;
    recordedAudio.value = null;
    audioChunks = [];
    duration.value = 0;

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Ваш браузер не поддерживает запись звука.');
      }

      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Set up Web Audio API Analyser for real-time visualization
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      audioContext = new AudioCtx();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 64;
      sourceNode = audioContext.createMediaStreamSource(mediaStream);
      sourceNode.connect(analyser);

      // MediaRecorder initialization
      let mimeType = 'audio/webm;codecs=opus';
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        if (MediaRecorder.isTypeSupported('audio/webm')) {
          mimeType = 'audio/webm';
        } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
          mimeType = 'audio/mp4';
        } else {
          mimeType = '';
        }
      }

      mediaRecorder = mimeType ? new MediaRecorder(mediaStream, { mimeType }) : new MediaRecorder(mediaStream);

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: mediaRecorder?.mimeType || 'audio/webm' });
        const audioUrl = URL.createObjectURL(audioBlob);
        
        recordedAudio.value = {
          id: 'rec-' + Date.now(),
          blob: audioBlob,
          url: audioUrl,
          duration: duration.value,
          createdAt: new Date().toISOString(),
          transcription: '«…сегодня сел и записал мысли голосом, наконец-то чувствую движение вперед.»',
          extractedFact: 'записана голосовая хроника — ' + duration.value + ' сек.',
        };

        cleanupAudioNodes();
      };

      mediaRecorder.start(250); // collect chunks every 250ms
      isRecording.value = true;
      isPaused.value = false;

      // Start timer
      timerInterval = window.setInterval(() => {
        if (!isPaused.value) {
          duration.value += 1;
          if (duration.value >= maxDuration) {
            stopRecording();
          }
        }
      }, 1000);

      // Start visualizer animation
      analyzeAudio();

    } catch (err: unknown) {
      console.error('Error starting audio recorder:', err);
      if (err instanceof Error) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          error.value = 'Доступ к микрофону запрещен. Пожалуйста, разрешите доступ к микрофону в настройках браузера.';
        } else if (err.name === 'NotFoundError') {
          error.value = 'Микрофон не обнаружен на вашем устройстве.';
        } else {
          error.value = err.message || 'Не удалось начать запись.';
        }
      } else {
        error.value = 'Не удалось получить доступ к микрофону.';
      }
      isRecording.value = false;
      cleanupAudioNodes();
    }
  };

  const pauseRecording = () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.pause();
      isPaused.value = true;
    }
  };

  const resumeRecording = () => {
    if (mediaRecorder && mediaRecorder.state === 'paused') {
      mediaRecorder.resume();
      isPaused.value = false;
      analyzeAudio();
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    isRecording.value = false;
    isPaused.value = false;
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  };

  const cancelRecording = () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.ondataavailable = null;
      mediaRecorder.onstop = null;
      mediaRecorder.stop();
    }
    isRecording.value = false;
    isPaused.value = false;
    duration.value = 0;
    recordedAudio.value = null;
    audioChunks = [];
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
    cleanupAudioNodes();
  };

  const cleanupAudioNodes = () => {
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }
    if (sourceNode) {
      sourceNode.disconnect();
      sourceNode = null;
    }
    if (audioContext && audioContext.state !== 'closed') {
      audioContext.close().catch(() => {});
      audioContext = null;
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }
    volumeLevel.value = 0;
    waveformBars.value = new Array(24).fill(10);
  };

  onUnmounted(() => {
    cleanupAudioNodes();
    if (timerInterval) {
      clearInterval(timerInterval);
    }
    if (recordedAudio.value?.url) {
      URL.revokeObjectURL(recordedAudio.value.url);
    }
  });

  return {
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
  };
}
