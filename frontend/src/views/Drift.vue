<template>
  <main class="content">
    <div class="page-header">
      <h2>Drift Monitor</h2>
      <p>Track drift-triggered retraining signals and acknowledgement state.</p>
    </div>
    <div class="card">
      <div class="card-head">
        <h3>Retraining Triggers</h3>
        <button @click="load">Refresh</button>
      </div>
      <table v-if="triggers.length">
        <thead><tr><th>ID</th><th>Score</th><th>Threshold</th><th>Dataset</th><th>Job</th><th>Status</th><th>Triggered</th></tr></thead>
        <tbody>
          <tr v-for="t in triggers" :key="t.id">
            <td>#{{ t.id }}</td>
            <td><span class="badge" :class="t.drift_score >= t.threshold ? 'badge-red' : 'badge-green'">{{ Number(t.drift_score).toFixed(3) }}</span></td>
            <td>{{ Number(t.threshold).toFixed(2) }}</td>
            <td>{{ t.dataset_id || '—' }}</td>
            <td>{{ t.training_job_id || '—' }}</td>
            <td>{{ t.acknowledged ? 'Acknowledged' : 'Open' }}</td>
            <td>{{ formatDate(t.triggered_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">No drift triggers yet. Drift alerts appear after enough inference samples cross the configured threshold.</div>
    </div>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api/client'

const triggers = ref([])
function formatDate(v) { return v ? new Date(v).toLocaleString() : '—' }
async function load() {
  const r = await api.get('/api/v1/mlops/drift-triggers', { limit: 50 })
  triggers.value = r.items || []
}
onMounted(load)
</script>

<style scoped>
.content { flex: 1; padding: 28px 32px; overflow-y: auto; }
.page-header { margin-bottom: 22px; }
.page-header h2 { font-size: 22px; }
.page-header p { color: var(--text2); }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; }
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
button { border: 1px solid var(--border); background: var(--surface2); color: var(--text); border-radius: 8px; padding: 8px 11px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--border); }
th { color: var(--text2); font-size: 11px; text-transform: uppercase; }
.badge { border-radius: 999px; padding: 3px 8px; font-size: 11px; font-weight: 700; }
.badge.green { color: var(--green); background: rgba(63,185,80,.12); }
.badge.red { color: var(--red); background: rgba(248,81,73,.13); }
.empty { text-align: center; padding: 34px; color: var(--text2); }
</style>
