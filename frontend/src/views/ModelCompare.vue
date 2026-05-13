<template>
  <main class="content">
    <div class="page-header"><h2>Model Comparison</h2><p>Compare two models side-by-side: benchmarks, latency, tokens, drift.</p></div>

    <div class="controls">
      <div class="field"><label>Model A</label><input v-model="modelA" placeholder="e.g., llama-3-8b" list="models" /></div>
      <datalist id="models"><option v-for="m in modelList" :key="m" :value="m" /></datalist>
      <div class="field"><label>Model B</label><input v-model="modelB" placeholder="e.g., mistral-7b" /></div>
      <button class="btn btn-primary" @click="compare" :disabled="loading">{{ loading ? 'Comparing...' : 'Compare' }}</button>
    </div>

    <div v-if="cardA && cardB" class="comparison">
      <div class="card" v-for="(card, side) in {A: cardA, B: cardB}" :key="side">
        <h3>{{ side === 'A' ? modelA : modelB }} <span class="badge" v-if="card.best">{{ card.best }}</span></h3>
        <div class="stats-grid">
          <div class="stat-card"><span>Requests</span><strong>{{ card.usage.total_requests }}</strong></div>
          <div class="stat-card"><span>Latency</span><strong>{{ card.usage.avg_latency_ms }}ms</strong></div>
          <div class="stat-card"><span>Tokens/Req</span><strong>{{ card.usage.avg_tokens }}</strong></div>
          <div class="stat-card"><span>Drift</span><strong>{{ card.usage.avg_drift }}</strong></div>
        </div>
        <div v-if="card.benchmarks.length" class="benchmarks">
          <h4>Benchmarks</h4>
          <div v-for="b in card.benchmarks" :key="b.suite" class="bench-row">
            <span>{{ b.suite }}</span>
            <span :class="b.passed ? 'pass' : 'fail'">{{ Math.round(b.score*100) }}%</span>
          </div>
        </div>
      </div>

      <div class="winner-card">
        <h3>Winner</h3>
        <div v-for="w in winner" :key="w.metric" class="winner-row">
          <span class="metric">{{ w.metric }}</span>
          <span class="winner-name">{{ w.winner }}</span>
          <span class="delta" :class="w.delta > 0 ? 'badge-green' : 'badge-red'">{{ w.delta > 0 ? '+' : '' }}{{ w.delta }}{{ w.unit }}</span>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">Enter two model names and click "Compare" to see side-by-side analysis.</div>
  </main>
</template>

<script setup>
import { ref, computed } from 'vue'
import api from '../api/client'

const modelA = ref('')
const modelB = ref('')
const loading = ref(false)
const modelList = ref([])
const cardA = ref(null)
const cardB = ref(null)

async function compare() {
  loading.value = true
  try {
    const [a, b] = await Promise.all([
      api.get(`/api/v1/models/card/${encodeURIComponent(modelA.value)}`),
      api.get(`/api/v1/models/card/${encodeURIComponent(modelB.value)}`),
    ])
    const ca = { usage: a.usage || {}, benchmarks: a.benchmarks || [], best: '' }
    const cb = { usage: b.usage || {}, benchmarks: b.benchmarks || [], best: '' }

    const a_lat = ca.usage.avg_latency_ms || 999
    const b_lat = cb.usage.avg_latency_ms || 999
    const a_drift = ca.usage.avg_drift || 1
    const b_drift = cb.usage.avg_drift || 1

    if (a_lat < b_lat) ca.best = '🏆 Best Latency'
    else if (b_lat < a_lat) cb.best = '🏆 Best Latency'
    if (a_drift < b_drift) ca.best = (ca.best || '') + ' 🎯 Best Quality'

    cardA.value = ca
    cardB.value = cb
  } catch (e) {
    alert('Comparison failed: ' + (e?.detail || e?.message || e))
  } finally { loading.value = false }
}

const winner = computed(() => {
  if (!cardA.value || !cardB.value) return []
  const a = cardA.value.usage, b = cardB.value.usage
  return [
    { metric: 'Avg Latency', winner: (a.avg_latency_ms||0) < (b.avg_latency_ms||0) ? modelA.value : modelB.value, delta: Math.round(((b.avg_latency_ms||0)-(a.avg_latency_ms||0))), unit: 'ms' },
    { metric: 'Requests', winner: (a.total_requests||0) > (b.total_requests||0) ? modelA.value : modelB.value, delta: (a.total_requests||0)-(b.total_requests||0), unit: '' },
    { metric: 'Drift Score', winner: (a.avg_drift||1) < (b.avg_drift||1) ? modelA.value : modelB.value, delta: Math.round(((b.avg_drift||1)-(a.avg_drift||1))*100)/100, unit: '' },
  ]
})
</script>

<style scoped>
.controls { display: flex; gap: 12px; align-items: flex-end; margin-bottom: 20px; }
.field label { font-size: 10px; color: var(--text2); display: block; margin-bottom: 4px; }
.field input { padding: 8px 12px; background: var(--surface2); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px; min-width: 180px; }
button.primary { padding: 8px 20px; background: var(--accent); color: #fff; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; }
.comparison { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 12px 0; }
.stat { background: var(--surface2); border-radius: 8px; padding: 12px; text-align: center; }
.stat span { font-size: 10px; color: var(--text2); display: block; }
.stat strong { font-size: 18px; display: block; margin-top: 4px; color: var(--accent); }
.benchmarks { margin-top: 12px; } .bench-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 12px; border-bottom: 1px solid var(--border); }
.pass { color: var(--green); font-weight: 700; } .fail { color: var(--red); font-weight: 700; }
.badge { font-size: 11px; padding: 2px 8px; background: rgba(63,185,80,.15); color: var(--green); border-radius: 999px; }
.winner-card { background: var(--surface); border: 2px solid var(--accent); border-radius: 12px; padding: 16px; margin-top: 12px; }
.winner-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; border-bottom: 1px solid var(--border); }
.winner-row:last-child { border: none; }
.metric { width: 100px; color: var(--text2); font-size: 11px; }
.winner-name { flex: 1; font-weight: 700; }
.delta { font-family: monospace; } .green { color: var(--green); } .red { color: var(--red); }
.empty { padding: 60px; text-align: center; color: var(--text2); }
</style>
