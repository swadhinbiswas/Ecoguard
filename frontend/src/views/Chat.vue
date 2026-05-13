<template>
  <main class="content">
    <div class="page-header"><h2>Chat</h2><p>Real-time LLM chat with streaming.</p></div>

    <div class="chat-controls">
      <div class="field">
        <label>Model</label>
        <select v-model="model" class="model-switcher">
          <option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option>
        </select>
      </div>
      <div class="field field-sm">
        <label>Temperature</label>
        <input v-model.number="temperature" type="range" min="0" max="2" step="0.1" />
        <span class="range-val">{{ temperature }}</span>
      </div>
      <div class="field field-sm">
        <label>Max Tokens</label>
        <input v-model.number="maxTokens" type="range" min="16" max="2048" step="16" />
        <span class="range-val">{{ maxTokens }}</span>
      </div>
      <button class="btn btn-ghost btn-sm" @click="clearChat" :disabled="loading">Clear</button>
    </div>

    <div class="card chat-card">
      <div class="messages" ref="msgEl">
        <div v-for="(msg, i) in messages" :key="i" :class="['msg', msg.role]">
          <strong>{{ msg.role === 'user' ? 'You' : msg.model || 'Assistant' }}</strong>
          <div class="msg-text">{{ msg.content }}</div>
        </div>
        <div v-if="streaming" class="msg assistant">
          <strong>{{ model }}</strong>
          <div class="msg-text streaming">{{ streamText }}<span class="cursor">|</span></div>
        </div>
      </div>
      <div class="input-row">
        <textarea v-model="input" @keydown.enter.exact.prevent="send" placeholder="Type a message..." rows="2"></textarea>
        <button class="btn btn-primary" @click="send" :disabled="loading || !input.trim()">{{ loading ? '...' : 'Send' }}</button>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'

const input = ref('')
const messages = ref([])
const loading = ref(false)
const streaming = ref(false)
const streamText = ref('')
const msgEl = ref(null)
const model = ref('default')
const temperature = ref(0.7)
const maxTokens = ref(512)
const availableModels = ref(['default'])

onMounted(async () => {
  try {
    const r = await fetch('/v1/models', { credentials: 'include' })
    const data = await r.json()
    if (data.data?.length) {
      availableModels.value = data.data.map(m => m.id)
      model.value = data.data[0].id
    }
  } catch {}
})

function clearChat() { messages.value = []; streamText.value = '' }

async function send() {
  const prompt = input.value.trim()
  if (!prompt || loading.value) return
  input.value = ''
  loading.value = true
  streaming.value = true
  streamText.value = ''

  messages.value = [...messages.value, { role: 'user', content: prompt }]

  try {
    const r = await fetch('/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        model: model.value,
        messages: messages.value.map(m => ({ role: m.role, content: m.content })),
        max_tokens: maxTokens.value,
        temperature: temperature.value,
        stream: true,
      }),
    })

    const reader = r.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let full = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const d = line.slice(6)
        if (d === '[DONE]') continue
        try {
          const chunk = JSON.parse(d)
          full += chunk.choices?.[0]?.delta?.content || ''
          streamText.value = full
        } catch {}
      }
    }

    if (full) messages.value = [...messages.value, { role: 'assistant', model: model.value, content: full }]
    streamText.value = ''
    await nextTick()
    if (msgEl.value) msgEl.value.scrollTop = msgEl.value.scrollHeight
  } catch {
    messages.value = [...messages.value, { role: 'assistant', content: '[Error]' }]
  } finally {
    loading.value = false
    streaming.value = false
  }
}
</script>

<style scoped>
.chat-controls { display: flex; gap: 16px; align-items: flex-end; margin-bottom: 16px; flex-wrap: wrap; }
.field label { display: block; font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: .5px; margin-bottom: 4px; font-weight: 600; }
.field-sm { width: 130px; }
.model-switcher {
  padding: 8px 12px; background: var(--surface2); border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: var(--text); font-size: 13px; min-width: 180px;
}
input[type="range"] { width: 100%; accent-color: var(--accent); }
.range-val { font-size: 11px; color: var(--text2); margin-left: 6px; font-family: monospace; }
.chat-card { min-height: 500px; display: flex; flex-direction: column; }
.messages { flex: 1; overflow-y: auto; padding: 16px; max-height: 460px; }
.msg { margin-bottom: 14px; }
.msg strong { display: block; font-size: 10px; color: var(--text3); margin-bottom: 4px; text-transform: uppercase; letter-spacing: .5px; }
.msg-text { padding: 10px 14px; border-radius: var(--radius); font-size: 13px; line-height: 1.6; white-space: pre-wrap; }
.msg.user .msg-text { background: var(--accent-muted); border: 1px solid rgba(59,130,246,0.2); }
.msg.assistant .msg-text { background: var(--surface2); border: 1px solid var(--border); }
.streaming { border-color: var(--accent) !important; }
.cursor { animation: blink 1s step-end infinite; color: var(--accent); }
@keyframes blink { 50% { opacity: 0; } }
.input-row { display: flex; gap: 10px; padding: 14px; border-top: 1px solid var(--border); }
.input-row textarea { flex: 1; padding: 10px; background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: 13px; resize: none; }
.input-row textarea:focus { outline: none; border-color: var(--accent); }
</style>
