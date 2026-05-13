<template>
  <main class="content">
    <div class="page-header"><h2>Backup &amp; Restore</h2><p>Manage backups and disaster recovery operations.</p></div>
    <div class="split">
      <div class="card">
        <h3>Create Backup</h3>
        <div class="field"><label><input type="checkbox" v-model="includeModels" /> Include models in backup</label></div>
        <button class="btn btn-primary" @click="createBackup" :disabled="backingUp">{{ backingUp ? 'Backing up...' : 'Create Backup Now' }}</button>
        <div v-if="backupResult" class="result-box"><pre>{{ backupResult }}</pre></div>
      </div>
      <div class="card">
        <h3>Existing Backups</h3>
        <button @click="loadBackups" class="mb">Refresh</button>
        <table v-if="backups.length"><thead><tr><th>Timestamp</th><th>Records</th><th>Size</th><th>Actions</th></tr></thead>
        <tbody><tr v-for="b in backups" :key="b.file">
          <td>{{ b.timestamp?.slice(0,19) || b.file }}</td>
          <td>{{ b.total_records }}</td>
          <td>{{ formatSize(b.size_bytes) }}</td>
          <td><button @click="restoreBackup(b.file)">Restore</button></td>
        </tr></tbody></table>
        <div v-else class="empty-state">No backups yet.</div>
      </div>
    </div>
    <div class="card" style="margin-top:12px">
      <h3>Daily Digest</h3>
      <button @click="loadDigest" class="mb">Generate</button>
      <div v-if="digest" class="stats-grid">
        <div class="stat-card"><span>Requests</span><strong>{{ digest.total_requests }}</strong></div>
        <div class="stat-card"><span>Tokens</span><strong>{{ digest.total_tokens }}</strong></div>
        <div class="stat-card"><span>Avg Latency</span><strong>{{ digest.avg_latency_ms }}ms</strong></div>
        <div class="stat-card"><span>Cost</span><strong>${{ digest.estimated_cost }}</strong></div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api/client'

const includeModels = ref(false)
const backingUp = ref(false)
const backupResult = ref('')
const backups = ref([])
const digest = ref(null)

async function createBackup() { backingUp.value=true; try { const r=await api.post('/api/v1/backup?include_models='+includeModels.value); backupResult.value=JSON.stringify(r,null,2) } catch(e) { backupResult.value=e.toString() } finally { backingUp.value=false } }
async function loadBackups() { const r=await api.get('/api/v1/backup/list'); backups.value=r.backups||[] }
async function restoreBackup(file) { try { await api.post('/api/v1/backup/restore?backup_file=./backups/'+file); alert('Restore initiated') } catch(e) { alert('Restore failed: '+e) } }
async function loadDigest() { digest.value = await api.get('/api/v1/digest') }
function formatSize(bytes) { return bytes ? (bytes<1024?bytes+'B':(bytes<1048576?(bytes/1024).toFixed(1)+'KB':(bytes/1048576).toFixed(1)+'MB')) : '-' }
</script>

<style scoped>
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.field { margin-bottom: 10px; }
.field label { font-size: 12px; color: var(--text); display: flex; align-items: center; gap: 6px; }
button.primary { padding: 10px 20px; background: var(--accent); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; }
button { padding: 8px 16px; border: 1px solid var(--border); background: var(--surface2); color: var(--text); border-radius: 6px; cursor: pointer; font-size: 12px; }
.mb { margin-bottom: 10px; }
.result-box { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-top: 10px; font-size: 11px; white-space: pre-wrap; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 10px; }
.stat { background: var(--surface2); border-radius: 8px; padding: 14px; text-align: center; }
.stat span { font-size: 10px; color: var(--text2); display: block; }
.stat strong { font-size: 20px; display: block; margin-top: 4px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th { text-align: left; padding: 8px; border-bottom: 1px solid var(--border); color: var(--text2); font-size: 10px; }
td { padding: 8px; border-bottom: 1px solid var(--border); }
.empty { padding: 40px; text-align: center; color: var(--text2); font-size: 12px; }
</style>
