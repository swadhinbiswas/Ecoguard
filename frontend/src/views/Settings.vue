<template>
  <main class="content">
    <div class="page-header"><h2>Settings</h2><p>API keys, notifications, and system preferences.</p></div>

    <div class="split">
      <div class="card">
        <h3>API Keys</h3>
        <div v-if="keys.length" class="key-list">
          <div v-for="k in keys" :key="k.id" class="key-row">
            <div class="key-info">
              <strong>{{ k.name }}</strong>
              <span class="key-preview">{{ k.preview }}</span>
            </div>
            <div class="key-meta">
              <span v-if="k.expires_at" class="expiry">Expires {{ k.expires_at }}</span>
              <span v-if="k.last_used">Last: {{ k.last_used }}</span>
            </div>
            <span class="key-scopes">
              <span v-for="s in (k.scopes||[])" :key="s" class="scope-tag">{{ s }}</span>
            </span>
            <button class="btn btn-danger" @click="revokeKey(k.id)">Revoke</button>
          </div>
        </div>
        <div v-if="!keys.length" class="empty-state">No API keys configured.</div>
        <div class="gen-row">
          <input v-model="newKeyName" placeholder="Key name (e.g., production)" class="gen-input" />
          <button @click="generateKey" :disabled="generating">{{ generating ? '...' : 'Generate' }}</button>
        </div>
      </div>

      <div class="card">
        <h3>Notification Channels</h3>
        <div class="field"><label>Slack Webhook URL</label><input v-model="channels.slack" placeholder="https://hooks.slack.com/..." /></div>
        <div class="field"><label>Discord Webhook URL</label><input v-model="channels.discord" placeholder="https://discord.com/api/webhooks/..." /></div>
        <div class="field"><label>Telegram Bot Token</label><input v-model="channels.telegram" placeholder="123456:ABC-DEF..." /></div>
        <div class="field"><label>Telegram Chat ID</label><input v-model="channels.telegramChat" placeholder="-100123456" /></div>
        <div class="field"><label>MS Teams Webhook URL</label><input v-model="channels.teams" placeholder="https://...webhook.office.com/..." /></div>
        <button class="btn btn-primary" @click="saveChannels">Save Channels</button>
        <button class="mb" @click="testNotify('slack')" style="margin-left:8px">Test Slack</button>
        <button class="mb" @click="testNotify('telegram')">Test Telegram</button>
      </div>
    </div>

    <div class="card" style="margin-top:12px">
      <h3>System Configuration</h3>
      <div class="config-grid">
        <div v-for="c in configList" :key="c.key" class="config-row">
          <label>{{ c.key }}</label>
          <input v-model="c.value" @change="updateConfig(c)" />
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client'

const keys = ref([])
const newKeyName = ref('')
const generating = ref(false)
const channels = ref({ slack:'', discord:'', telegram:'', telegramChat:'', teams:'' })
const configList = ref([])

async function loadKeys() { try { const r = await api.get('/api/v1/keys/analytics'); keys.value = r.keys || [] } catch {} }
async function generateKey() { generating.value=true; try { await api.post('/api/v1/enterprise/keys/generate', { name: newKeyName.value }); newKeyName.value=''; await loadKeys() } catch{} finally { generating.value=false } }
async function revokeKey(id) { await api.delete(`/api/v1/enterprise/keys/${id}`); await loadKeys() }
async function saveChannels() { localStorage.setItem('ecoguard-channels', JSON.stringify(channels.value)) }
async function testNotify(channel) {
  const msg = 'Test notification from Eco-Guard'
  const url = channel==='slack' ? channels.value.slack : channel==='discord' ? channels.value.discord : channels.value.telegram ? `https://api.telegram.org/bot${channels.value.telegram}/sendMessage?chat_id=${channels.value.telegramChat}&text=${encodeURIComponent(msg)}` : ''
  if (!url) return alert('No URL configured')
  try { await api.post('/api/v1/notify/chat', { message:msg, platform: channel==='telegram'?'discord':channel, webhook_url:url }); alert('Sent!') }
  catch(e) { alert('Failed: '+e) }
}
async function updateConfig(c) { try { await api.put('/api/v1/system/config', { key:c.key, value:c.value }) } catch {} }
async function loadConfig() {
  try { const r = await api.get('/api/v1/system/config'); configList.value = Object.entries(r).map(([k,v])=>({key:k, value:String(v)})) } catch {}
}
onMounted(() => { loadKeys(); loadConfig(); const saved = localStorage.getItem('ecoguard-channels'); if (saved) channels.value = JSON.parse(saved) })
</script>

<style scoped>
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.key-list { max-height: 300px; overflow-y: auto; }
.key-row { display: flex; align-items: center; gap: 8px; padding: 8px; border-bottom: 1px solid var(--border); font-size: 12px; flex-wrap: wrap; }
.key-info { flex: 1; } .key-preview { font-size: 10px; color: var(--text2); font-family: monospace; display: block; }
.key-meta { font-size: 10px; color: var(--text2); } .expiry { color: var(--yellow); }
.scope-tag { font-size: 9px; padding: 1px 5px; background: var(--surface2); border-radius: 3px; margin: 0 2px; }
.gen-row { display: flex; gap: 8px; margin-top: 12px; }
.gen-input { flex:1; padding: 8px; background: var(--surface2); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 12px; }
.field { margin-bottom: 10px; } .field label { font-size: 10px; color: var(--text2); display: block; margin-bottom: 4px; }
.field input { width: 100%; padding: 8px; background: var(--surface2); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 12px; }
button { padding: 8px 16px; border-radius: 6px; font-size: 12px; border: 1px solid var(--border); background: var(--surface2); color: var(--text); cursor: pointer; }
button.primary { background: var(--accent); color: #fff; border: none; }
button.danger { background: var(--red); color: #fff; border: none; } .mb { margin-bottom: 8px; }
.config-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.config-row { display: flex; flex-direction: column; } .config-row label { font-size: 10px; color: var(--text2); }
.config-row input { padding: 6px; background: var(--surface2); border: 1px solid var(--border); border-radius: 4px; color: var(--text); font-size: 11px; }
.empty { padding: 20px; text-align: center; color: var(--text2); font-size: 12px; }
</style>
