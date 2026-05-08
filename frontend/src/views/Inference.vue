<template>
  <main class="content">
    <div class="page-header">
      <h2>Inference Analytics</h2>
      <p>Recent request volume, latency, tokens, and drift from the gateway.</p>
    </div>
    <div class="stats-grid">
      <div class="stat" v-for="s in stats" :key="s.label">
        <span>{{ s.label }}</span>
        <strong>{{ s.value }}</strong>
        <small>{{ s.sub }}</small>
      </div>
    </div>
    <div class="card">
      <div class="card-head">
        <h3>Recent Requests</h3>
        <button @click="load" :disabled="loading">{{ loading ? 'Refreshing...' : 'Refresh' }}</button>
      </div>
      <table v-if="logs.length">
        <thead><tr><th>Request ID</th><th>Latency</th><th>Tokens</th><th>Drift</th><th>Time</th></tr></thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id">
            <td class="mono">{{ log.request_id }}</td>
            <td>{{ formatMs(log.latency_ms) }}</td>
            <td>{{ log.token_count }}</td>
            <td><span class="badge" :class="driftClass(log.drift_score)">{{ formatDrift(log.drift_score) }}</span></td>
            <td>{{ formatDate(log.timestamp) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">No inference logs yet. Send requests to <code>/api/v1/predict</code> to populate this page.</div>
    </div>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api/client'

const loading = ref(false)
const logs = ref([])
const stats = ref([])

function formatMs(v) { return v == null ? '—' : `${Number(v).toFixed(1)} ms` }
function formatDrift(v) { return v == null ? '—' : Number(v).toFixed(3) }
function formatDate(v) { return v ? new Date(v).toLocaleString() : '—' }
function driftClass(v) {
  if (v == null) return 'blue'
  if (v >= 0.8) return 'red'
  if (v >= 0.5) return 'yellow'
  return 'green'
}

async function load() {
  loading.value = true
  try {
    const [summary, adminStats, recent] = await Promise.all([
      api.get('/api/v1/metrics/summary'),
      api.get('/api/v1/admin/stats', { hours: 24 }),
      api.get('/api/v1/admin/logs', { hours: 24, limit: 25 }),
    ])
    logs.value = recent.items || []
    stats.value = [
      { label: '24h Requests', value: adminStats.total_requests, sub: 'Logged completions' },
      { label: 'Avg Latency', value: formatMs(adminStats.avg_latency_ms), sub: 'Last 24 hours' },
      { label: 'Avg Tokens', value: adminStats.avg_tokens, sub: 'Per response' },
      { label: 'Model', value: summary.model_loaded ? 'Loaded' : 'Offline', sub: summary.model_loaded ? 'Ready' : 'Connect backend' },
    ]
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.content { flex: 1; padding: 28px 32px; overflow-y: auto; }
.page-header { margin-bottom: 22px; }
.page-header h2 { font-size: 22px; }
.page-header p, small { color: var(--text2); }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 16px; }
.stat, .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); }
.stat { padding: 16px; display: grid; gap: 4px; }
.stat span { color: var(--text2); font-size: 11px; text-transform: uppercase; letter-spacing: .5px; }
.stat strong { font-size: 24px; }
.card { padding: 18px; }
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
button { border: 1px solid var(--border); background: var(--surface2); color: var(--text); border-radius: 8px; padding: 8px 11px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--border); }
th { color: var(--text2); font-size: 11px; text-transform: uppercase; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.badge { border-radius: 999px; padding: 3px 8px; font-size: 11px; font-weight: 700; }
.badge.green { color: var(--green); background: rgba(63,185,80,.12); }
.badge.yellow { color: var(--yellow); background: rgba(210,153,34,.13); }
.badge.red { color: var(--red); background: rgba(248,81,73,.13); }
.badge.blue { color: var(--accent); background: rgba(77,166,255,.13); }
.empty { text-align: center; padding: 34px; color: var(--text2); }
code { color: var(--accent); }
</style>
