<template>
  <main class="content">
    <div class="page-header"><h2>Model Registry</h2><p>Manage model versions</p></div>
    <div class="card" v-if="!items.length"><div class="empty-state">No models registered yet</div></div>
    <div class="card" v-else><table><thead><tr><th>Name</th><th>Version</th><th>Status</th><th>Base Model</th></tr></thead>
    <tbody><tr v-for="m in items" :key="m.id"><td><strong>{{ m.name }}</strong></td><td class="mono">{{ m.version }}</td><td><span class="badge" :class="statusClass(m.status)">{{ m.status }}</span></td><td>{{ m.base_model || '—' }}</td></tr></tbody></table></div>
  </main>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client'
const items = ref([])
function statusClass(s) { return { production: 'badge-green', staging: 'badge-yellow', archived: 'badge-red' }[s] || 'badge-blue' }
onMounted(async () => { try { const r = await api.get('/api/v1/mlops/models'); items.value = r.items } catch {} })
</script>
<style scoped>
.content { flex: 1; padding: 28px 32px; overflow-y: auto; }
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 22px; font-weight: 700; }
.page-header p { color: var(--text2); font-size: 13px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 10px 12px; color: var(--text2); font-size: 11px; text-transform: uppercase; border-bottom: 1px solid var(--border); }
td { padding: 12px; border-bottom: 1px solid var(--border); }
.mono { font-family: monospace; font-size: 12px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge.green { background: rgba(63,185,80,.15); color: var(--green); }
.badge.yellow { background: rgba(210,153,34,.15); color: var(--yellow); }
.badge.red { background: rgba(248,81,73,.15); color: var(--red); }
.badge.blue { background: rgba(77,166,255,.15); color: var(--accent); }
.empty { text-align: center; padding: 40px; color: var(--text2); }
</style>
