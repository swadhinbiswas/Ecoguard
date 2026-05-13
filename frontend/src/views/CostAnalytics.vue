<template>
  <main class="content">
    <div class="page-header"><h2>Cost Analytics</h2><p>Token spend, cost trends, and per-model breakdown.</p></div>

    <div class="stats-grid">
      <div class="stat-card" v-for="s in stats" :key="s.label"><span>{{ s.label }}</span><strong>{{ s.value }}</strong></div>
    </div>

    <div class="split">
      <div class="card">
        <h3>Cost Per Model (24h)</h3>
        <div class="bar-chart">
          <div v-for="m in modelCosts" :key="m.model" class="bar-row">
            <span class="bar-label">{{ m.model }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{width: m.pct + '%'}"></div>
            </div>
            <span class="bar-val">${{ m.cost.toFixed(6) }}</span>
          </div>
          <div v-if="!modelCosts.length" class="empty-state">No cost data yet.</div>
        </div>
      </div>

      <div class="card">
        <h3>Compare Providers</h3>
        <div class="field"><label>Prompt</label><textarea v-model="comparePrompt" rows="2" placeholder="Enter a prompt to compare costs..." /></div>
        <div class="field" style="width:100px"><label>Max Tokens</label><input v-model.number="compareTokens" type="number" /></div>
        <button @click="compare" :disabled="comparing">{{ comparing ? '...' : 'Compare' }}</button>
        <div v-if="comparison" class="compare-table">
          <div v-for="p in comparison.providers" :key="p.provider" class="compare-row" :class="{ self: p.self_hosted }">
            <span class="c-name">{{ p.provider }}</span>
            <span class="c-cost">${{ p.total_cost.toFixed(6) }}</span>
            <span v-if="p.self_hosted" class="c-tag">self-hosted</span>
          </div>
          <div v-if="comparison.cheapest" class="best">Cheapest: {{ comparison.cheapest }}</div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:12px">
      <h3>Export Data</h3>
      <div class="btn-row">
        <button @click="exportCSV('logs')">Export Logs CSV</button>
        <button @click="exportCSV('feedback')">Export Feedback CSV</button>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../api/client'

const summary = ref({})
const usage = ref({ series: [] })
const modelCosts = ref([])
const comparePrompt = ref('Explain quantum computing in simple terms')
const compareTokens = ref(128)
const comparing = ref(false)
const comparison = ref(null)

const stats = computed(() => [
  { label:'Total Requests', value: summary.value.total_requests||0 },
  { label:'Total Tokens', value: (summary.value.total_tokens||0).toLocaleString() },
  { label:'Est. Cost', value: '$'+(summary.value.estimated_cost||0).toFixed(4) },
  { label:'Period', value: summary.value.period_hours+'h' },
])

async function load() {
  summary.value = await api.get('/api/v1/cost/usage', { hours: 24 })
}
async function compare() {
  comparing.value = true
  try { comparison.value = await api.post('/api/v1/cost/compare', { prompt: comparePrompt.value, max_tokens: compareTokens.value }) }
  catch(e) { comparison.value = { error: e.message } }
  finally { comparing.value = false }
}
function exportCSV(type) { window.open(`/api/v1/export/${type}/csv`, '_blank') }
onMounted(load)
</script>

<style scoped>
.stats-grid { display: grid; grid-template-columns: repeat(4,1fr); gap:12px; margin-bottom:16px; }
.stat { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; text-align: center; }
.stat span { font-size:10px; color:var(--text2); display:block; }
.stat strong { font-size:22px; color:var(--accent); display:block; margin-top:4px; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.bar-row { display:flex; align-items:center; gap:8px; padding:3px 0; }
.bar-label { font-size:11px; width:60px; text-align:right; color:var(--text2); }
.bar-track { flex:1; height:14px; background:var(--bg); border-radius:3px; overflow:hidden; }
.bar-fill { height:100%; background:var(--accent); border-radius:3px; min-width:2px; }
.bar-val { font-size:11px; color:var(--text2); width:80px; text-align:right; }
.field { margin-bottom:8px; } .field label { font-size:10px; color:var(--text2); text-transform:uppercase; display:block; margin-bottom:4px; }
.field textarea, .field input { width:100%; padding:8px; background:var(--surface2); border:1px solid var(--border); border-radius:6px; color:var(--text); font-size:12px; }
button { padding:8px 16px; background:var(--accent); color:#fff; border:none; border-radius:6px; cursor:pointer; font-size:12px; }
button:disabled { opacity:.5; }
.compare-table { margin-top:12px; }
.compare-row { display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid var(--border); font-size:12px; }
.compare-row.self { background:rgba(63,185,80,.05); }
.c-name { flex:1; } .c-cost { font-weight:700; font-family:monospace; } .c-tag { font-size:9px; padding:2px 6px; background:var(--green); color:#fff; border-radius:4px; }
.best { margin-top:8px; padding:8px; background:rgba(63,185,80,.1); border:1px solid rgba(63,185,80,.3); border-radius:6px; font-size:12px; color:var(--green); }
.btn-row { display:flex; gap:8px; }
.empty { padding:20px; text-align:center; color:var(--text2); font-size:12px; }
</style>
