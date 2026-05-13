<template>
  <main class="content">
    <div class="page-header"><h2>Analytics</h2><p>Usage patterns, cost trends, and latency distribution.</p></div>

    <div class="stats-grid">
      <div class="stat-card" v-for="s in stats" :key="s.label"><span>{{ s.label }}</span><strong>{{ s.value }}</strong></div>
    </div>

    <div class="card">
      <h3>Usage Over Time</h3>
      <div class="controls"><select v-model="hours"><option :value="24">24h</option><option :value="168">7 days</option><option :value="720">30 days</option></select><button @click="loadUsage">Load</button></div>
      <div v-if="usageSeries.length" class="chart">
        <div class="bar-row" v-for="d in usageSeries.slice(-50)" :key="d.timestamp">
          <span class="bar-label">{{ d.timestamp.slice(11,16) || d.timestamp.slice(0,10) }}</span>
          <div class="bar" :style="{width: Math.max(1,(d.requests/Math.max(1,maxReq))*100)+'%'}"></div>
          <span class="bar-val">{{ d.requests }}</span>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:12px"><h3>Top Prompts</h3><table v-if="topPrompts.length"><thead><tr><th>Prompt</th><th>Count</th><th>Avg Latency</th><th>Avg Tokens</th></tr></thead><tbody><tr v-for="p in topPrompts" :key="p.prompt"><td class="code">{{ p.prompt.slice(0,80) }}</td><td>{{ p.count }}</td><td>{{ p.avg_latency_ms }}ms</td><td>{{ p.avg_tokens }}</td></tr></tbody></table></div>
  </main>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../api/client'

const hours = ref(168)
const summary = ref({})
const usageSeries = ref([])
const topPrompts = ref([])

const maxReq = computed(() => Math.max(1, ...usageSeries.value.map(d=>d.requests)))
const stats = computed(() => [
  { label:'Requests', value: summary.value.total_requests || 0 },
  { label:'Avg Latency', value: (summary.value.avg_latency_ms || 0)+'ms' },
  { label:'Avg Tokens', value: summary.value.avg_tokens || 0 },
  { label:'Drift Events', value: summary.value.drift_events || 0 },
])

async function loadAll() {
  summary.value = await api.get('/api/v1/analytics/summary', { hours: hours.value })
  const usage = await api.get('/api/v1/analytics/usage', { hours: hours.value, interval: hours.value <= 24 ? 15 : 60 })
  usageSeries.value = usage.series || []
  const tp = await api.get('/api/v1/analytics/top-prompts', { limit: 5 })
  topPrompts.value = tp.prompts || []
}
async function loadUsage() { await loadAll() }

onMounted(loadAll)
</script>

<style scoped>
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.stat { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; text-align: center; }
.stat span { display: block; font-size: 10px; color: var(--text2); margin-bottom: 4px; }
.stat strong { font-size: 22px; color: var(--accent); }
.controls { display: flex; gap: 8px; margin-bottom: 12px; }
.controls select, .controls button { padding: 6px 12px; background: var(--surface2); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 12px; }
.chart { max-height: 400px; overflow-y: auto; }
.bar-row { display: flex; align-items: center; gap: 8px; padding: 2px 0; }
.bar-label { font-size: 10px; color: var(--text2); width: 50px; text-align: right; }
.bar { height: 16px; background: var(--accent); border-radius: 3px; min-width: 2px; transition: width .3s; }
.bar-val { font-size: 10px; color: var(--text2); margin-left: 4px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th { text-align: left; padding: 8px; border-bottom: 1px solid var(--border); color: var(--text2); font-size: 10px; text-transform: uppercase; }
td { padding: 8px; border-bottom: 1px solid var(--border); } .code { font-family: monospace; font-size: 11px; }
</style>
