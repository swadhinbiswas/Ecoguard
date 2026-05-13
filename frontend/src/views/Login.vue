<template>
  <div class="login-page">
    <div v-if="system.demo_mode" class="demo-ribbon">Public demo · read-only workspace</div>
    <div class="login-box">
      <div class="brand">Eco-Guard</div>
      <p class="sub">Self-hosted LLM gateway and MLOps control plane</p>
      <div v-if="system.demo_mode" class="demo-card">
        <strong>Try the demo</strong>
        <span>Use <code>{{ demoUsername }}</code> / <code>{{ demoPassword }}</code>. Destructive actions are disabled.</span>
        <button type="button" class="ghost-btn" @click="fillDemo">Use demo login</button>
      </div>
      <div v-if="error" class="error-box">{{ error }}</div>
      <form @submit.prevent="handleLogin">
        <div class="field"><label>Username</label><input v-model="username" required autofocus /></div>
        <div class="field"><label>Password</label><input v-model="password" type="password" required /></div>
        <button type="submit" class="btn" :disabled="loading">{{ loading ? 'Signing in...' : 'Sign In' }}</button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'
import api from '../api/client'

const auth = useAuthStore()
const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const demoUsername = ref('')
const demoPassword = ref('')
const system = ref({ demo_mode: false })

function fillDemo() {
  if (demoUsername.value) username.value = demoUsername.value
  if (demoPassword.value) password.value = demoPassword.value
}

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.message || 'Invalid credentials'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    system.value = await api.get('/api/v1/system/status')
  } catch {}
})
</script>

<style scoped>
.login-page { display: flex; align-items: center; justify-content: center; min-height: 100vh; width: 100%; background: radial-gradient(circle at 20% 10%, rgba(77,166,255,.18), transparent 28%), radial-gradient(circle at 90% 80%, rgba(63,185,80,.12), transparent 30%), var(--bg); padding: 20px; }
.demo-ribbon { position: fixed; top: 18px; right: 18px; border: 1px solid rgba(77,166,255,.35); background: rgba(77,166,255,.12); color: var(--accent); padding: 8px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.login-box { background: rgba(20,27,34,.92); border: 1px solid var(--border); border-radius: 18px; padding: 40px; width: 100%; max-width: 430px; box-shadow: 0 24px 80px rgba(0,0,0,.35); backdrop-filter: blur(14px); }
.brand { font-size: 28px; font-weight: 800; color: var(--accent); margin-bottom: 4px; }
.sub { color: var(--text2); font-size: 13px; margin-bottom: 24px; }
.demo-card { display: grid; gap: 8px; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; padding: 14px; margin-bottom: 18px; font-size: 13px; color: var(--text2); }
.demo-card strong { color: var(--text); font-size: 14px; }
.demo-card code { color: var(--green); background: rgba(63,185,80,.1); padding: 2px 5px; border-radius: 5px; }
.ghost-btn { border: 1px solid var(--border); background: transparent; color: var(--text); border-radius: 8px; padding: 9px 10px; font-weight: 700; }
.ghost-btn:hover { border-color: var(--accent); color: var(--accent); }
.err { background: rgba(248,81,73,.1); border: 1px solid rgba(248,81,73,.3); color: var(--red); padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 11px; color: var(--text2); text-transform: uppercase; letter-spacing: .5px; margin-bottom: 6px; }
.field input { width: 100%; padding: 12px; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 14px; }
.field input:focus { outline: none; border-color: var(--accent); }
.btn { width: 100%; padding: 12px; border-radius: 8px; border: none; font-size: 14px; font-weight: 600; background: var(--accent); color: #fff; margin-top: 8px; }
.btn:disabled { opacity: .6; }
</style>
