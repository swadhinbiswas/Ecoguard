<template>
  <main class="content">
    <div class="page-header">
      <h2>Training Jobs</h2>
      <p>Queued, running, completed, failed, and cancelled fine-tuning jobs.</p>
    </div>
    <div class="card">
      <div class="card-head">
        <h3>Job Queue</h3>
        <button @click="load">Refresh</button>
      </div>
      <table v-if="jobs.length">
        <thead><tr><th>Name</th><th>Status</th><th>Trigger</th><th>Started</th><th>Completed</th><th>Error</th></tr></thead>
        <tbody>
          <tr v-for="job in jobs" :key="job.id">
            <td><strong>{{ job.name }}</strong><div class="mono">#{{ job.id }}</div></td>
            <td><span class="badge" :class="statusClass(job.status)">{{ job.status }}</span></td>
            <td>{{ job.trigger_type || 'manual' }}</td>
            <td>{{ formatDate(job.started_at) }}</td>
            <td>{{ formatDate(job.completed_at) }}</td>
            <td class="err">{{ job.error_message || '—' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">No jobs yet. Drift-triggered and manual jobs will appear here.</div>
    </div>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api/client'

const jobs = ref([])
function formatDate(v) { return v ? new Date(v).toLocaleString() : '—' }
function statusClass(status) {
  return { queued: 'blue', running: 'yellow', completed: 'green', failed: 'red', cancelled: 'gray' }[status] || 'blue'
}
async function load() {
  const r = await api.get('/api/v1/mlops/jobs', { limit: 50 })
  jobs.value = r.items || []
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
th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { color: var(--text2); font-size: 11px; text-transform: uppercase; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.badge { border-radius: 999px; padding: 3px 8px; font-size: 11px; font-weight: 700; }
.badge.green { color: var(--green); background: rgba(63,185,80,.12); }
.badge.yellow { color: var(--yellow); background: rgba(210,153,34,.13); }
.badge.red { color: var(--red); background: rgba(248,81,73,.13); }
.badge.blue { color: var(--accent); background: rgba(77,166,255,.13); }
.badge.gray { color: var(--text2); background: rgba(137,151,169,.13); }
.err { max-width: 260px; color: var(--text2); }
.empty { text-align: center; padding: 34px; color: var(--text2); }
</style>
