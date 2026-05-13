<template>
  <main class="content">
    <div class="page-header">
      <h2>Datasets</h2>
      <p>Fine-tuning datasets created from inference logs.</p>
    </div>
    <div class="stats-grid">
      <div class="stat-card"><span>Total Datasets</span><strong>{{ stats.total_datasets ?? 0 }}</strong></div>
      <div class="stat-card"><span>Total Records</span><strong>{{ stats.total_records ?? 0 }}</strong></div>
    </div>
    <div class="card">
      <div class="card-head">
        <h3>Dataset Registry</h3>
        <button @click="load">Refresh</button>
      </div>
      <table v-if="datasets.length">
        <thead><tr><th>Name</th><th>Version</th><th>Records</th><th>Quality</th><th>Created</th></tr></thead>
        <tbody>
          <tr v-for="d in datasets" :key="d.id">
            <td><strong>{{ d.name }}</strong></td>
            <td class="mono">{{ d.version }}</td>
            <td>{{ d.record_count }}</td>
            <td>{{ formatPercent(d.quality_score) }}</td>
            <td>{{ formatDate(d.created_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">No datasets yet. Use the dataset API or drift pipeline to create one from inference logs.</div>
    </div>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api/client'

const datasets = ref([])
const stats = ref({})
function formatDate(v) { return v ? new Date(v).toLocaleString() : '—' }
function formatPercent(v) { return v == null ? '—' : `${Math.round(Number(v) * 100)}%` }
async function load() {
  const [list, s] = await Promise.all([
    api.get('/api/v1/mlops/datasets', { limit: 50 }),
    api.get('/api/v1/mlops/datasets/stats'),
  ])
  datasets.value = list.items || []
  stats.value = s || {}
}
onMounted(load)
</script>

<style scoped>
.content { flex: 1; padding: 28px 32px; overflow-y: auto; }
.page-header { margin-bottom: 22px; }
.page-header h2 { font-size: 22px; }
.page-header p { color: var(--text2); }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 16px; }
.stat, .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); }
.stat { padding: 16px; display: grid; gap: 4px; }
.stat span { color: var(--text2); font-size: 11px; text-transform: uppercase; }
.stat strong { font-size: 24px; }
.card { padding: 18px; }
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
button { border: 1px solid var(--border); background: var(--surface2); color: var(--text); border-radius: 8px; padding: 8px 11px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--border); }
th { color: var(--text2); font-size: 11px; text-transform: uppercase; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.empty { text-align: center; padding: 34px; color: var(--text2); }
</style>
