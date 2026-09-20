import { ref, onMounted, onUnmounted } from 'vue';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
}

export function usePWAInstall() {
  const deferredPrompt = ref<BeforeInstallPromptEvent | null>(null);
  const isInstalled = ref(false);
  const isIOS = ref(false);

  const handleBeforeInstallPrompt = (e: Event) => {
    e.preventDefault();
    deferredPrompt.value = e as BeforeInstallPromptEvent;
  };

  const handleAppInstalled = () => {
    isInstalled.value = true;
    deferredPrompt.value = null;
  };

  onMounted(() => {
    // Detect standalone mode (already installed)
    const isStandalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      (window.navigator as any).standalone === true;
    isInstalled.value = isStandalone;

    // Detect iOS devices
    const userAgent = window.navigator.userAgent.toLowerCase();
    const isIOSDevice = /iphone|ipad|ipod/.test(userAgent);
    isIOS.value = isIOSDevice;

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);
  });

  onUnmounted(() => {
    window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.removeEventListener('appinstalled', handleAppInstalled);
  });

  const install = async () => {
    if (!deferredPrompt.value) return false;
    await deferredPrompt.value.prompt();
    const { outcome } = await deferredPrompt.value.userChoice;
    if (outcome === 'accepted') {
      isInstalled.value = true;
      deferredPrompt.value = null;
      return true;
    }
    return false;
  };

  return {
    deferredPrompt,
    isInstalled,
    isIOS,
    install,
  };
}
