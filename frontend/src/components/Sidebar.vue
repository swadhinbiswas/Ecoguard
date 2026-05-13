<template>
  <aside class="sidebar">
    <div class="logo">
      <svg class="logo-svg" viewBox="0 0 64 64" fill="none">
        <path d="M32 4L56 14v18c0 16-10.67 22.67-24 28C18.67 54.67 8 48 8 32V14L32 4Z" fill="url(#lg)" stroke="url(#lg)" stroke-width="1.5" stroke-linejoin="round"/>
        <path d="M32 10l18 7.5v13c0 11.5-7.5 17-18 21-10.5-4-18-9.5-18-21v-13L32 10Z" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="0.8"/>
        <circle cx="32" cy="22" r="2.5" fill="url(#lg)"/><circle cx="25" cy="30" r="2" fill="url(#lg)"/><circle cx="39" cy="30" r="2" fill="url(#lg)"/><circle cx="32" cy="38" r="2" fill="url(#lg)"/><circle cx="21" cy="46" r="1.8" fill="url(#lg)"/><circle cx="43" cy="46" r="1.8" fill="url(#lg)"/>
        <line x1="32" y1="22" x2="25" y2="30" stroke="url(#lg)" stroke-width="1.2" stroke-linecap="round"/>
        <line x1="32" y1="22" x2="39" y2="30" stroke="url(#lg)" stroke-width="1.2" stroke-linecap="round"/>
        <line x1="25" y1="30" x2="32" y2="38" stroke="url(#lg)" stroke-width="1" stroke-linecap="round"/>
        <line x1="39" y1="30" x2="32" y2="38" stroke="url(#lg)" stroke-width="1" stroke-linecap="round"/>
        <line x1="32" y1="38" x2="21" y2="46" stroke="url(#lg)" stroke-width="0.9" stroke-linecap="round"/>
        <line x1="32" y1="38" x2="43" y2="46" stroke="url(#lg)" stroke-width="0.9" stroke-linecap="round"/>
        <defs><linearGradient id="lg" x1="8" y1="4" x2="56" y2="60"><stop stop-color="#3b82f6"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs>
      </svg>
      <div>
        <h1>Eco-Guard</h1>
        <span>{{ demoMode ? 'Read-only demo' : 'MLOps Platform' }}</span>
      </div>
    </div>
    <nav>
      <router-link to="/dashboard" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><rect x="1" y="7" width="4" height="8" rx="1" fill="currentColor"/><rect x="6" y="3" width="4" height="12" rx="1" fill="currentColor"/><rect x="11" y="5" width="4" height="10" rx="1" fill="currentColor"/></svg> Overview</router-link>
      <router-link to="/chat" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><path d="M2 1a1 1 0 00-1 1v10a1 1 0 001 1h4l2 3 2-3h4a1 1 0 001-1V2a1 1 0 00-1-1H2z" fill="currentColor"/></svg> Chat</router-link>
      <router-link to="/models" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><path d="M2 2a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V4a2 2 0 00-2-2H2zm1 3h10v1H3V5zm0 3h10v1H3V8zm0 3h6v1H3v-1z" fill="currentColor"/></svg> Model Registry</router-link>
      <router-link to="/inference" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><path d="M5.5 1a.5.5 0 01.5.5v2a.5.5 0 01-.5.5h-3a.5.5 0 01-.5-.5v-2a.5.5 0 01.5-.5h3zm6 6a.5.5 0 01.5.5v2a.5.5 0 01-.5.5h-3a.5.5 0 01-.5-.5v-2a.5.5 0 01.5-.5h3zm-8 5a.5.5 0 01.5.5v2a.5.5 0 01-.5.5h-3a.5.5 0 01-.5-.5v-2a.5.5 0 01.5-.5h3zM2 1l3 3-3 3" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg> Inference</router-link>

      <div class="nav-section">MLOps</div>
      <router-link to="/experiments" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><path d="M14 1a1 1 0 011 1v12a1 1 0 01-1 1H2a1 1 0 01-1-1V2a1 1 0 011-1h12zM5 12V5l-1.5 3L2 5v7h1V7l1.5 3L6 7v5H5zm4-6H8v1h2v1H8v3H7V6h2z" fill="currentColor"/></svg> Experiments</router-link>
      <router-link to="/jobs" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><path d="M6.5 1a.5.5 0 01.5.5V2h2v-.5a.5.5 0 011 0V2h2a1 1 0 011 1v1H3V3a1 1 0 011-1h2v-.5a.5.5 0 01.5-.5zM3 5h10v9a1 1 0 01-1 1H4a1 1 0 01-1-1V5zm3 2v5h1V7H6zm3 0v5h1V7H9z" fill="currentColor"/></svg> Training Jobs</router-link>
      <router-link to="/datasets" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><path d="M7.5 1a.5.5 0 01.5.5V4h5.5a.5.5 0 01.5.5v10a.5.5 0 01-.5.5H2.5a.5.5 0 01-.5-.5v-10a.5.5 0 01.5-.5H7V1.5a.5.5 0 01.5-.5z" fill="currentColor"/></svg> Datasets</router-link>
      <router-link to="/eval" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><path d="M13.5 1.5a.5.5 0 01.5.5v12a.5.5 0 01-.5.5h-11a.5.5 0 01-.5-.5v-12a.5.5 0 01.5-.5h11zM11 5l-4 4-2-2-3 3" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg> Eval Builder</router-link>
      <router-link to="/finetune" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><path d="M11.5 1.5L14 4l-9 9-3.5.5L2 10l9.5-8.5zM5 10l1 1" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg> Fine-Tuning</router-link>
      <router-link to="/templates" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><path d="M2 2h5l2 2h5v10H2V2z" fill="currentColor"/></svg> Prompt Library</router-link>
      <router-link to="/drift" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><path d="M1 15L5 7l3 4 3-6 4 8" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg> Drift Monitor</router-link>

      <div class="nav-section">Analytics</div>
      <router-link to="/analytics" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><rect x="1" y="9" width="3" height="6" rx="1" fill="currentColor"/><rect x="5" y="5" width="3" height="10" rx="1" fill="currentColor"/><rect x="9" y="2" width="3" height="13" rx="1" fill="currentColor"/><rect x="13" y="7" width="2" height="8" rx="1" fill="currentColor"/></svg> Analytics</router-link>
      <router-link to="/cost" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" stroke-width="1.5"/><text x="8" y="11" text-anchor="middle" font-size="9" fill="currentColor" font-weight="700">$</text></svg> Cost</router-link>
      <router-link to="/logs" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><path d="M2 3h12M2 7h12M2 11h12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg> Live Logs</router-link>

      <div class="nav-section">System</div>
      <router-link to="/backup" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 4v4l3 2" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg> Backup</router-link>
      <router-link to="/compare" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><rect x=".5" y="1.5" width="6" height="13" rx="1" fill="currentColor"/><rect x="9.5" y="5.5" width="6" height="9" rx="1" fill="currentColor"/></svg> Compare</router-link>
      <router-link to="/settings" class="nav-item"><svg viewBox="0 0 16 16" class="icon"><circle cx="8" cy="8" r="2.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 1v2m0 10v2M1 8h2m10 0h2M2.5 2.5l1.5 1.5m8 8l1.5 1.5M13.5 2.5l-1.5 1.5m-8 8l-1.5 1.5" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg> Settings</router-link>
    </nav>
    <div class="live-metrics" v-if="metricsStore.connected">
      <div class="metric-row"><span>Latency</span><strong>{{ metricsStore.avgLatency }}ms</strong></div>
      <div class="metric-row"><span>Workers</span><strong>{{ metricsStore.concurrency.in_use }}/{{ metricsStore.concurrency.max }}</strong></div>
      <div class="metric-row"><span>Uptime</span><strong>{{ metricsStore.uptime }}</strong></div>
    </div>
    <div class="sidebar-footer">
      <div class="status"><span class="dot" :class="statusColor"></span>{{ statusText }}</div>
      <button @click="themeStore.toggle()" class="theme-btn">
        <svg v-if="themeStore.theme === 'dark'" viewBox="0 0 16 16" class="btn-icon"><circle cx="8" cy="8" r="4" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 1v2M8 13v2M1 8h2m10 0h2M2.5 2.5l1.5 1.5m8 8l1.5 1.5M13.5 2.5l-1.5 1.5m-8 8l-1.5 1.5" fill="none" stroke="currentColor" stroke-width="1"/></svg>
        <svg v-else viewBox="0 0 16 16" class="btn-icon"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 1.5A5.5 5.5 0 0113.5 8 5.5 5.5 0 018 13.5a5.5 5.5 0 110-11z" fill="currentColor"/></svg>
      </button>
      <button @click="logout" class="logout-btn">Sign Out</button>
    </div>
  </aside>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useMetricsStore } from '../stores/metrics'
import { useThemeStore } from '../stores/theme'
import { useRouter } from 'vue-router'
import api from '../api/client'

const auth = useAuthStore()
const metricsStore = useMetricsStore()
const themeStore = useThemeStore()
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

onMounted(() => { checkHealth(); setInterval(checkHealth, 15000); metricsStore.connect() })
</script>

<style scoped>
.sidebar {
  width: 230px; min-width: 230px; background: var(--surface);
  border-right: 1px solid var(--border); padding: 20px 0;
  display: flex; flex-direction: column; position: sticky; top: 0; height: 100vh;
}
.logo { padding: 0 18px 18px; border-bottom: 1px solid var(--border); margin-bottom: 10px; display: flex; align-items: center; gap: 12px; }
.logo-svg { width: 32px; height: 32px; flex-shrink: 0; }
.logo h1 { font-size: 17px; font-weight: 700; letter-spacing: -0.3px; }
.logo span { font-size: 10px; color: var(--text2); display: block; }
nav { flex: 1; padding: 0 10px; overflow-y: auto; }
.nav-item {
  display: flex; align-items: center; gap: 10px; padding: 8px 12px;
  border-radius: var(--radius-sm); color: var(--text2); text-decoration: none;
  font-size: 12px; font-weight: 500; margin-bottom: 1px;
  transition: all var(--transition); letter-spacing: -0.2px;
}
.nav-item:hover { background: var(--surface2); color: var(--text); transform: translateX(2px); }
.nav-item.router-link-active { background: var(--accent-muted); color: var(--accent); font-weight: 600; }
.nav-section { padding: 12px 12px 4px; font-size: 9px; color: var(--text3); text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
.icon { width: 14px; height: 14px; flex-shrink: 0; opacity: 0.6; transition: opacity var(--transition); }
.nav-item:hover .icon, .nav-item.router-link-active .icon { opacity: 1; }
.live-metrics { padding: 8px 18px; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.metric-row { display: flex; justify-content: space-between; align-items: center; padding: 3px 0; font-size: 10px; }
.metric-row span { color: var(--text2); }
.metric-row strong { color: var(--accent); font-weight: 600; font-family: 'SF Mono', 'Fira Code', monospace; font-size: 11px; }
.sidebar-footer { padding: 12px 18px; display: flex; flex-direction: column; gap: 8px; }
.status { font-size: 11px; display: flex; align-items: center; gap: 8px; }
.dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.dot.green { background: var(--green); }
.dot.red { background: var(--red); }
.logout-btn { width: 100%; padding: 7px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: transparent; color: var(--text2); font-size: 11px; cursor: pointer; transition: all var(--transition); }
.logout-btn:hover { background: var(--surface2); color: var(--text); border-color: var(--text3); }
.theme-btn { width: 100%; padding: 5px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: transparent; cursor: pointer; display: flex; justify-content: center; transition: all var(--transition); }
.theme-btn:hover { background: var(--surface2); border-color: var(--text3); }
.btn-icon { width: 16px; height: 16px; color: var(--text2); transition: color var(--transition); }
.theme-btn:hover .btn-icon { color: var(--text); }
</style>
