<template>
  <div class="login-page">
    <div class="login-box">
      <div class="brand">Eco-Guard</div>
      <p class="sub">MLOps Platform — Sign in</p>
      <div v-if="error" class="err">{{ error }}</div>
      <form @submit.prevent="handleLogin">
        <div class="field"><label>Username</label><input v-model="username" required autofocus /></div>
        <div class="field"><label>Password</label><input v-model="password" type="password" required /></div>
        <button type="submit" class="btn" :disabled="loading">{{ loading ? 'Signing in...' : 'Sign In' }}</button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push('/dashboard')
  } catch {
    error.value = 'Invalid credentials'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { display: flex; align-items: center; justify-content: center; min-height: 100vh; width: 100%; background: var(--bg); }
.login-box { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 40px; width: 100%; max-width: 400px; }
.brand { font-size: 28px; font-weight: 800; color: var(--accent); margin-bottom: 4px; }
.sub { color: var(--text2); font-size: 13px; margin-bottom: 24px; }
.err { background: rgba(248,81,73,.1); border: 1px solid rgba(248,81,73,.3); color: var(--red); padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 11px; color: var(--text2); text-transform: uppercase; letter-spacing: .5px; margin-bottom: 6px; }
.field input { width: 100%; padding: 12px; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 14px; }
.field input:focus { outline: none; border-color: var(--accent); }
.btn { width: 100%; padding: 12px; border-radius: 8px; border: none; font-size: 14px; font-weight: 600; background: var(--accent); color: #fff; margin-top: 8px; }
.btn:disabled { opacity: .6; }
</style>
