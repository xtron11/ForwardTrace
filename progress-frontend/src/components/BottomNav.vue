<template>
  <nav class="fixed bottom-0 left-0 w-full bg-bg-primary border-t border-border-color flex justify-center gap-8 sm:gap-16 py-4 z-50">
    <router-link to="/today" class="text-[11px] font-mono tracking-widest uppercase text-text-muted pb-1 border-b-2 border-transparent transition-colors hover:text-text-primary" active-class="!text-accent !border-accent">СЕГОДНЯ</router-link>
    <router-link to="/timeline" class="text-[11px] font-mono tracking-widest uppercase text-text-muted pb-1 border-b-2 border-transparent transition-colors hover:text-text-primary" active-class="!text-accent !border-accent">ХРОНИКА</router-link>
    <router-link to="/report" class="text-[11px] font-mono tracking-widest uppercase text-text-muted pb-1 border-b-2 border-transparent transition-colors hover:text-text-primary" active-class="!text-accent !border-accent">ОТЧЁТ</router-link>
    <router-link to="/goals" class="text-[11px] font-mono tracking-widest uppercase text-text-muted pb-1 border-b-2 border-transparent transition-colors hover:text-text-primary" active-class="!text-accent !border-accent">ЦЕЛИ</router-link>
  </nav>
</template>
