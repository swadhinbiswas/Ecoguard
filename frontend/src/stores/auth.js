import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { setToken } from '../api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('eco_token') || '')
  const user = ref(JSON.parse(localStorage.getItem('eco_user') || 'null'))

  const isAuthenticated = computed(() => !!token.value)

  async function login(username, password) {
    const url = new URL('/api/v1/auth/login', window.location.origin)
    url.searchParams.set('username', username)
    url.searchParams.set('password', password)
    const r = await fetch(url, { method: 'POST' })
    if (!r.ok) throw new Error('Invalid credentials')
    const data = await r.json()
    token.value = data.access_token
    user.value = { username, role: 'admin' }
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
