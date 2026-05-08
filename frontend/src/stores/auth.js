import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { setToken } from '../api/client'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('eco_token') || '')
  const user = ref(JSON.parse(localStorage.getItem('eco_user') || 'null'))

  const isAuthenticated = computed(() => !!token.value)

  async function login(username, password) {
    const r = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!r.ok) throw new Error('Invalid credentials')
    const data = await r.json()
    token.value = data.access_token
    user.value = { username, role: data.role || 'admin' }
    localStorage.setItem('eco_token', token.value)
    localStorage.setItem('eco_user', JSON.stringify(user.value))
    setToken(token.value)
    return true
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('eco_token')
    localStorage.removeItem('eco_user')
    setToken('')
  }

  function init() {
    if (token.value) setToken(token.value)
  }

  return { token, user, isAuthenticated, login, logout, init }
})
