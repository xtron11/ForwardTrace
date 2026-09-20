import { ref, computed } from 'vue';

export interface TimelineEntry {
  id: string;
  date: string;
  timestamp: number;
  duration: number; // in seconds
  audioUrl?: string;
  saidText: string;
  extractedFact: string;
  goalContext?: string;
}

const STORAGE_KEY = 'forwardtrace_timeline_entries';

const defaultEntries: TimelineEntry[] = [
  {
    id: 'entry-1',
    date: '3 сентября',
    timestamp: Date.now() - 86400000 * 2,
    duration: 28,
    saidText: '…всё равно закончил работу над прототипом и впервые показал его людям.',
    extractedFact: 'показал прототип людям — первый отклик со стороны',
    goalContext: 'Цель · довести прототип до людей',
  },
  {
    id: 'entry-2',
    date: '17 августа',
    timestamp: Date.now() - 86400000 * 18,
    duration: 31,
    saidText: '…сегодня опять отложил на завтра, но нашел критическую ошибку в конфиге.',
    extractedFact: 'обнаружил и локализовал ошибку в архитектуре',
    goalContext: 'Цель · довести прототип до людей',
  },
  {
    id: 'entry-3',
    date: '2 июля',
    timestamp: Date.now() - 86400000 * 60,
    duration: 25,
    saidText: '…не понимаю, куда иду, но решил делать по одной задаче в день без спешки.',
    extractedFact: 'сфокусировался на одном микрошаге в день',
    goalContext: 'Цель · довести прототип до людей',
  },
];

const loadEntries = (): TimelineEntry[] => {
  if (typeof window === 'undefined') return defaultEntries;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    }
  } catch (e) {
    console.error('Failed to parse timeline entries from localStorage', e);
  }
  return defaultEntries;
};

const entries = ref<TimelineEntry[]>(loadEntries());

const saveEntries = () => {
  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.value));
    } catch (e) {
      console.error('Failed to save timeline entries', e);
    }
  }
};

export function useTimelineStore() {
  const allEntries = computed(() => entries.value);
  const totalDays = computed(() => entries.value.length);
  const latestEntry = computed(() => entries.value[0] || null);

  const addEntry = (entry: Omit<TimelineEntry, 'id' | 'timestamp'>) => {
    const newEntry: TimelineEntry = {
      ...entry,
      id: 'entry-' + Date.now(),
      timestamp: Date.now(),
    };
    entries.value.unshift(newEntry);
    saveEntries();
    return newEntry;
  };

  const removeEntry = (id: string) => {
    entries.value = entries.value.filter((e) => e.id !== id);
    saveEntries();
  };

  return {
    entries: allEntries,
    totalDays,
    latestEntry,
    addEntry,
    removeEntry,
  };
}
