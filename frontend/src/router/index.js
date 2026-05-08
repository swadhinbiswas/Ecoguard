import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/models', name: 'Models', component: () => import('../views/Models.vue') },
  { path: '/inference', name: 'Inference', component: () => import('../views/Inference.vue') },
  { path: '/drift', name: 'Drift', component: () => import('../views/Drift.vue') },
  { path: '/experiments', name: 'Experiments', component: () => import('../views/Experiments.vue') },
  { path: '/jobs', name: 'Jobs', component: () => import('../views/Jobs.vue') },
  { path: '/datasets', name: 'Datasets', component: () => import('../views/Datasets.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  auth.init()
  if (to.meta.public) return next()
  if (!auth.isAuthenticated) return next('/login')
  next()
})

export default router
