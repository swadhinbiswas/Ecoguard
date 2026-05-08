<template>
  <aside class="sidebar">
    <div class="logo">
      <div class="logo-icon">E</div>
      <div>
        <h1>Eco-Guard</h1>
        <span>{{ demoMode ? 'Public demo' : 'MLOps Platform' }}</span>
      </div>
    </div>
    <div v-if="demoMode" class="demo-pill">Read-only demo</div>
    <nav>
      <router-link to="/dashboard" class="nav-item">
        <span class="icon">▣</span> Overview
      </router-link>
      <router-link to="/models" class="nav-item">
        <span class="icon">⬡</span> Model Registry
      </router-link>
      <router-link to="/inference" class="nav-item">
        <span class="icon">⚡</span> Inference
      </router-link>
      <router-link to="/drift" class="nav-item">
        <span class="icon">📈</span> Drift Monitor
      </router-link>
      <router-link to="/experiments" class="nav-item">
        <span class="icon">🧪</span> Experiments
      </router-link>
      <router-link to="/jobs" class="nav-item">
        <span class="icon">⚙</span> Training Jobs
      </router-link>
      <router-link to="/datasets" class="nav-item">
        <span class="icon">📦</span> Datasets
      </router-link>
    </nav>
    <div class="sidebar-footer">
      <div class="status">
        <span class="dot" :class="statusColor"></span>
        {{ statusText }}
      </div>
      <button @click="logout" class="logout-btn">Sign Out</button>
    </div>
  </aside>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'
import api from '../api/client'

const auth = useAuthStore()
const router = useRouter()
const modelLoaded = ref(false)
const version = ref('')
const demoMode = ref(false)

const statusColor = computed(() => modelLoaded.value ? 'green' : 'red')
const statusText = computed(() => modelLoaded.value ? 'Model Online' : 'Model Offline')

async function checkHealth() {
  try {
    const data = await api.get('/api/v1/health')
    const system = await api.get('/api/v1/system/status')
    modelLoaded.value = data.checks?.model === 'loaded'
    version.value = data.version || ''
    demoMode.value = Boolean(system.demo_mode)
  } catch {}
}

function logout() {
  auth.logout()
  router.push('/login')
}

onMounted(() => { checkHealth(); setInterval(checkHealth, 15000) })
</script>

<style scoped>
.sidebar {
  width: 240px; min-width: 240px; background: var(--surface);
  border-right: 1px solid var(--border); padding: 20px 0;
  display: flex; flex-direction: column; position: sticky; top: 0; height: 100vh;
}
.logo { padding: 0 20px 20px; border-bottom: 1px solid var(--border); margin-bottom: 12px; display: flex; align-items: center; gap: 10px; }
.logo-icon { width: 32px; height: 32px; background: var(--accent); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 700; font-size: 16px; }
.logo h1 { font-size: 17px; color: var(--accent); font-weight: 700; }
.logo span { font-size: 11px; color: var(--text2); display: block; }
.demo-pill { margin: 0 20px 14px; border: 1px solid rgba(210,153,34,.35); background: rgba(210,153,34,.1); color: var(--yellow); border-radius: 999px; padding: 7px 10px; font-size: 11px; font-weight: 800; text-align: center; text-transform: uppercase; letter-spacing: .6px; }
nav { flex: 1; padding: 0 12px; }
.nav-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  border-radius: 8px; color: var(--text2); text-decoration: none;
  font-size: 13px; font-weight: 500; margin-bottom: 2px; transition: all .15s;
}
.nav-item:hover { background: var(--surface2); color: var(--text); }
.nav-item.router-link-active { background: var(--accent); color: #fff; }
.icon { font-size: 16px; width: 20px; text-align: center; }
.sidebar-footer { padding: 16px 20px; border-top: 1px solid var(--border); }
.status { font-size: 12px; display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot.green { background: var(--green); }
.dot.red { background: var(--red); }
.logout-btn { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid var(--border); background: transparent; color: var(--text2); font-size: 12px; }
.logout-btn:hover { background: var(--surface2); color: var(--text); }
</style>
