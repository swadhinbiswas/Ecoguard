import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/models', name: 'Models', component: () => import('../views/Models.vue') },
  { path: '/inference', name: 'Inference', component: () => import('../views/Inference.vue') },
  { path: '/chat', name: 'Chat', component: () => import('../views/Chat.vue') },
  { path: '/drift', name: 'Drift', component: () => import('../views/Drift.vue') },
  { path: '/experiments', name: 'Experiments', component: () => import('../views/Experiments.vue') },
  { path: '/jobs', name: 'Jobs', component: () => import('../views/Jobs.vue') },
  { path: '/datasets', name: 'Datasets', component: () => import('../views/Datasets.vue') },
  { path: '/eval', name: 'Eval Builder', component: () => import('../views/EvalBuilder.vue') },
  { path: '/finetune', name: 'Fine-Tune', component: () => import('../views/FineTune.vue') },
  { path: '/templates', name: 'Templates', component: () => import('../views/Templates.vue') },
  { path: '/analytics', name: 'Analytics', component: () => import('../views/Analytics.vue') },
  { path: '/cost', name: 'Cost Analytics', component: () => import('../views/CostAnalytics.vue') },
  { path: '/logs', name: 'Live Logs', component: () => import('../views/LiveLogs.vue') },
  { path: '/backup', name: 'Backup', component: () => import('../views/Backup.vue') },
  { path: '/settings', name: 'Settings', component: () => import('../views/Settings.vue') },
  { path: '/compare', name: 'Model Comparison', component: () => import('../views/ModelCompare.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()
  if (to.meta.public) return next()
  if (!auth.isAuthenticated) {
    await auth.checkAuth()
  }
  if (!auth.isAuthenticated) return next('/login')
  next()
})

export default router
