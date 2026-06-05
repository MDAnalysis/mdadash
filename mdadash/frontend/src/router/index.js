import { createRouter, createWebHistory } from 'vue-router'

import DashboardView from '@/views/DashboardView.vue'
import AlertsView from '@/views/AlertsView.vue'
import SettingsView from '@/views/SettingsView.vue'

export const routes = [
  { path: '/', component: DashboardView, meta: { title: 'Dashboard' } },
  { path: '/alerts', component: AlertsView, meta: { title: 'Alerts' } },
  { path: '/settings', component: SettingsView, meta: { title: 'Settings' } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
