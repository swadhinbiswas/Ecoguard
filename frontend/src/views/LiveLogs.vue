<template>
  <main class="content">
    <div class="page-header"><h2>Live Log Viewer</h2><p>Real-time inference log streaming via WebSocket.</p></div>

    <div class="controls">
      <button @click="toggleStream">{{ streaming ? '⏸ Pause' : '▶ Start' }}</button>
      <button @click="clear" class="btn btn-ghost">Clear</button>
      <span class="count">{{ logs.length }} entries</span>
    </div>

    <div class="log-container" ref="logEl">
      <div v-for="(log, i) in logs" :key="i" :class="['log-line', log.drift_score >= 0.8 ? 'drift' : '']">
        <span class="time">{{ formatTime(log.timestamp) }}</span>
        <span class="rid">{{ (log.request_id || '').slice(0,12) }}</span>
        <span class="latency">{{ log.latency_ms || 0 }}ms</span>
        <span class="tokens">{{ log.token_count || 0 }}t</span>
        <span v-if="log.drift_score !== null" class="drift-score">drift:{{ (log.drift_score || 0).toFixed(2) }}</span>
        <span class="prompt">{{ truncate(log.input_text, 80) }}</span>
      </div>
    </div>

    <div class="card" style="margin-top:12px">
      <h3>Audit Trail</h3>
      <button @click="loadAudit" class="mb">Load Recent</button>
      <div v-for="e in auditEntries" :key="e.id" class="audit-row">
        <span class="audit-time">{{ e.timestamp?.slice(11,19) }}</span>
        <span class="audit-action">{{ e.action }}</span>
        <span v-if="e.username">by {{ e.username }}</span>
        <span v-if="e.resource_type" class="audit-resource">{{ e.resource_type }}/{{ e.resource_id }}</span>
      </div>
      <div v-if="!auditEntries.length" class="empty-state">No audit entries yet.</div>
    </div>
  </main>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import api from '../api/client'

const logs = ref([])
const streaming = ref(false)
const auditEntries = ref([])
let ws = null
let reconnectTimer = null

function connect() {
  if (ws?.readyState === WebSocket.OPEN) return
  ws = new WebSocket(`ws://${window.location.host}/ws/metrics`)
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (data.latency?.recent?.length) {
        const now = Date.now()
        data.latency.recent.forEach(lat => {
          logs.value.unshift({
            timestamp: now, latency_ms: lat,
            request_id: 'live-' + Math.random().toString(36).slice(2,8),
            token_count: 0, drift_score: null, input_text: 'Live metric sample'
          })
        })
        if (logs.value.length > 200) logs.value = logs.value.slice(0, 200)
        nextTick(() => { const el = document.querySelector('.log-container'); if (el) el.scrollTop = 0 })
      }
    } catch {}
  }
  ws.onclose = () => { if (streaming.value) { reconnectTimer = setTimeout(connect, 2000) } }
  ws.onerror = () => ws?.close()
}

function toggleStream() { streaming.value = !streaming.value; if (streaming.value) connect(); else { clearTimeout(reconnectTimer); ws?.close() } }
function clear() { logs.value = [] }
function formatTime(ts) { return new Date(ts).toLocaleTimeString() }
function truncate(s, n) { return (s || '').slice(0, n) + ((s||'').length > n ? '...' : '') }

async function loadAudit() {
  const r = await api.get('/api/v1/audit/entries', { hours: 1, limit: 50 })
  auditEntries.value = r.entries || []
}

onUnmounted(() => { clearTimeout(reconnectTimer); ws?.close() })
</script>

<style scoped>
.controls { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
button { padding: 8px 16px; background: var(--accent); color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; }
.ghost { background: transparent; border: 1px solid var(--border); color: var(--text); }
.count { font-size: 11px; color: var(--text2); }
.log-container { max-height: 400px; overflow-y: auto; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; }
.log-line { display: flex; gap: 8px; padding: 4px 10px; font-size: 11px; font-family: monospace; border-bottom: 1px solid rgba(48,54,61,.3); }
.log-line.drift { background: rgba(248,81,73,.08); }
.time { color: var(--text2); width: 75px; }
.rid { color: var(--accent); width: 110px; }
.latency { color: var(--yellow); width: 55px; text-align: right; }
.tokens { color: var(--green); width: 35px; text-align: right; }
.drift-score { color: var(--red); width: 80px; }
.prompt { color: var(--text); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.audit-row { display: flex; gap: 8px; padding: 4px 0; font-size: 11px; border-bottom: 1px solid var(--border); }
.audit-time { color: var(--text2); width: 60px; }
.audit-action { color: var(--accent); font-weight: 600; width: 120px; }
.audit-resource { color: var(--text2); font-size: 10px; }
.mb { margin-bottom: 8px; }
.empty { padding: 20px; text-align: center; color: var(--text2); font-size: 12px; }
</style>
