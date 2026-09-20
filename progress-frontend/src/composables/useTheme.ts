import { ref, watchEffect } from 'vue';

const savedTheme = typeof window !== 'undefined' ? localStorage.getItem('theme') : null;
// Default to dark theme as in forward-trace.com design
const isDark = ref(savedTheme !== null ? savedTheme === 'dark' : true);

const applyTheme = (dark: boolean) => {
  if (typeof document === 'undefined') return;

  const updateClasses = () => {
    // Apply dark mode class directly on the body tag as requested
    if (document.body) {
      if (dark) {
        document.body.classList.add('dark');
        document.body.classList.remove('light');
      } else {
        document.body.classList.remove('dark');
        document.body.classList.add('light');
      }
    }

    // Also update documentElement for full Tailwind & CSS variable compatibility
    if (document.documentElement) {
      if (dark) {
        document.documentElement.classList.add('dark');
        document.documentElement.classList.remove('light');
      } else {
        document.documentElement.classList.remove('dark');
        document.documentElement.classList.add('light');
      }
    }

    // Update meta theme-color for browser chrome
    const metaThemeColor = document.querySelector('meta[name="theme-color"]');
    if (metaThemeColor) {
      metaThemeColor.setAttribute('content', dark ? '#0A1022' : '#F4F7FC');
    }
  };

  updateClasses();
  // Ensure if body wasn't ready yet (early run), it applies once DOM loads
  if (!document.body && typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', updateClasses, { once: true });
  }
};

const toggleDark = () => {
  isDark.value = !isDark.value;
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light');
  applyTheme(isDark.value);
};

// Reactively keep theme synchronized
watchEffect(() => {
  applyTheme(isDark.value);
});

export function useTheme() {
  return { isDark, toggleDark };
}

