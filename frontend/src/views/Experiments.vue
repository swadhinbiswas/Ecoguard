<template>
  <main class="content">
    <div class="page-header">
      <h2>Experiment Tracking</h2>
      <p>Training experiments, best metrics, and current lifecycle status.</p>
    </div>
    <div class="card">
      <div class="card-head">
        <h3>Experiments</h3>
        <button @click="load">Refresh</button>
      </div>
      <table v-if="experiments.length">
        <thead><tr><th>Name</th><th>Status</th><th>Base Model</th><th>Best Metric</th><th>Started</th></tr></thead>
        <tbody>
          <tr v-for="exp in experiments" :key="exp.id">
            <td><strong>{{ exp.name }}</strong><div class="mono">#{{ exp.id }}</div></td>
            <td><span class="badge" :class="statusClass(exp.status)">{{ exp.status }}</span></td>
            <td>{{ exp.base_model }}</td>
            <td>{{ metricText(exp) }}</td>
            <td>{{ formatDate(exp.started_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">No experiments yet. Create training jobs or log experiment metrics to populate this view.</div>
    </div>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api/client'

const experiments = ref([])
function formatDate(v) { return v ? new Date(v).toLocaleString() : '—' }
function metricText(exp) {
  if (!exp.best_metric) return '—'
  return `${exp.best_metric}: ${Number(exp.best_metric_value).toFixed(4)}`
}
function statusClass(status) {
  return { running: 'yellow', completed: 'green', failed: 'red', cancelled: 'gray' }[status] || 'blue'
}
async function load() {
  const r = await api.get('/api/v1/mlops/experiments', { limit: 50 })
  experiments.value = r.items || []
}
onMounted(load)
</script>

<style scoped>
.content { flex: 1; padding: 28px 32px; overflow-y: auto; }
.page-header { margin-bottom: 22px; }
.page-header h2 { font-size: 22px; }
.page-header p, .mono { color: var(--text2); }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; }
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
button { border: 1px solid var(--border); background: var(--surface2); color: var(--text); border-radius: 8px; padding: 8px 11px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--border); }
th { color: var(--text2); font-size: 11px; text-transform: uppercase; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.badge { border-radius: 999px; padding: 3px 8px; font-size: 11px; font-weight: 700; }
.badge.green { color: var(--green); background: rgba(63,185,80,.12); }
.badge.yellow { color: var(--yellow); background: rgba(210,153,34,.13); }
.badge.red { color: var(--red); background: rgba(248,81,73,.13); }
.badge.blue { color: var(--accent); background: rgba(77,166,255,.13); }
.badge.gray { color: var(--text2); background: rgba(137,151,169,.13); }
.empty { text-align: center; padding: 34px; color: var(--text2); }
</style>
