import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const isAuthenticated = computed(() => !!user.value)

  async function checkAuth() {
    try {
      const r = await fetch(`${API_BASE}/api/v1/auth/status`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        credentials: 'include',
      })
      if (!r.ok) { user.value = null; return false }
      const data = await r.json()
      if (data.authenticated) {
        user.value = { username: data.user, role: data.role || 'viewer' }
        return true
      }
      user.value = null
      return false
    } catch {
      user.value = null
      return false
    }
  }

  async function login(username, password) {
    const r = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ username, password }),
    })
    if (!r.ok) {
      const data = await r.json().catch(() => ({}))
      throw new Error(data?.error?.message || data?.detail || 'Invalid credentials')
    }
    const data = await r.json()
    user.value = { username, role: data.role || 'admin' }
    return true
  }

  async function logout() {
    await fetch(`${API_BASE}/api/v1/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {})
    user.value = null
  }

  async function init() {
    await checkAuth()
  }

  return { user, isAuthenticated, login, logout, init, checkAuth }
})
