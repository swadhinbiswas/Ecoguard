<template>
  <main class="content">
    <div class="page-header">
      <h2>Platform Overview</h2>
      <p>Real-time monitoring of your LLM inference platform</p>
    </div>
    <div class="stats-grid">
      <div class="stat" v-for="s in stats" :key="s.label">
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-value" :style="{ color: s.color }">{{ s.value }}</div>
        <div class="stat-sub">{{ s.sub }}</div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client'

const stats = ref([])

onMounted(async () => {
  try {
    const h = await api.get('/api/v1/health')
    const s = await api.get('/api/v1/metrics/summary')
    stats.value = [
      { label: 'Database', value: h.checks?.database === 'up' ? 'Connected' : 'Down', color: h.checks?.database === 'up' ? 'var(--green)' : 'var(--red)', sub: '' },
      { label: 'Model', value: s.model_loaded ? 'Loaded' : 'Offline', color: s.model_loaded ? 'var(--green)' : 'var(--red)', sub: '' },
      { label: 'Rate Limiting', value: s.rate_limit_enabled ? 'Active' : 'Off', color: s.rate_limit_enabled ? 'var(--accent)' : 'var(--text2)', sub: '' },
      { label: 'Cache', value: `${s.cache_size} entries`, color: 'var(--accent)', sub: s.cache_enabled ? 'Enabled' : 'Disabled' },
      { label: 'Drift Samples', value: s.drift_samples, color: 'var(--purple)', sub: 'In window' },
      { label: 'Version', value: h.version || '—', color: 'var(--text)', sub: h.service || '' },
    ]
  } catch {}
})
</script>

<style scoped>
.content { flex: 1; padding: 28px 32px; overflow-y: auto; }
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 22px; font-weight: 700; }
.page-header p { color: var(--text2); font-size: 13px; margin-top: 2px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }
.stat { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px 20px; }
.stat-label { font-size: 11px; color: var(--text2); text-transform: uppercase; letter-spacing: .5px; }
.stat-value { font-size: 26px; font-weight: 700; margin: 4px 0; }
.stat-sub { font-size: 12px; color: var(--text2); }
</style>
