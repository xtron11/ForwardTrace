import { createRouter, createWebHistory } from 'vue-router';
import LandingPage from '../views/LandingPage.vue';
import AppLayout from '../layouts/AppLayout.vue';
import TodayView from '../views/TodayView.vue';
import TimelineView from '../views/TimelineView.vue';
import ReportView from '../views/ReportView.vue';
import GoalsView from '../views/GoalsView.vue';
import SettingsPage from '../views/SettingsPage.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: LandingPage
    },
    {
      path: '/',
      component: AppLayout,
      children: [
        {
          path: 'today',
          name: 'today',
          component: TodayView
        },
        {
          path: 'timeline',
          name: 'timeline',
          component: TimelineView
        },
        {
          path: 'report',
          name: 'report',
          component: ReportView
        },
        {
          path: 'goals',
          name: 'goals',
          component: GoalsView
        },
        {
          path: 'settings',
          name: 'settings',
          component: SettingsPage
        }
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/today'
    }
  ],
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    }
    return { top: 0 };
  }
});

export default router;
