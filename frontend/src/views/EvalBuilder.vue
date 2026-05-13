<template>
  <main class="content">
    <div class="page-header">
      <h2>Eval Builder</h2>
      <p>Define evaluation suites and criteria — no code needed.</p>
    </div>

    <div class="split">
      <div class="card">
        <h3>Create Eval Suite</h3>
        <div class="field"><label>Suite Name</label><input v-model="suiteName" placeholder="e.g., accuracy-baseline" /></div>

        <div class="eval-criteria-list">
          <div v-for="(c, i) in testCases" :key="i" class="criteria-card">
            <div class="criteria-head">
              <span class="num">#{{ i + 1 }}</span>
              <button class="remove" @click="testCases.splice(i,1)">×</button>
            </div>
            <div class="field"><label>Prompt</label><textarea v-model="c.prompt" rows="2" placeholder="Enter test prompt..." /></div>
            <div class="row">
              <div class="field" style="flex:1"><label>Check Type</label>
                <select v-model="c.check">
                  <option value="contains">Contains</option>
                  <option value="regex">Regex</option>
                  <option value="exact">Exact Match</option>
                  <option value="similar">Semantic Similar</option>
                </select>
              </div>
              <div class="field" style="flex:2"><label>Expected / Pattern</label><input v-model="c.expected" placeholder="Expected text or regex" /></div>
            </div>
            <div class="row">
              <div class="field" style="flex:1"><label>Max Tokens</label><input v-model.number="c.max_tokens" type="number" /></div>
              <div class="field" style="flex:1"><label>Temperature</label><input v-model.number="c.temperature" type="number" step="0.1" /></div>
            </div>
          </div>
        </div>

        <button class="add" @click="addCase">+ Add Test Case</button>

        <div class="actions">
          <button class="btn btn-primary" @click="registerSuite" :disabled="!suiteName || !testCases.length || saving">
            {{ saving ? 'Registering...' : 'Register Suite' }}
          </button>
          <button class="btn btn-primary" @click="runSuite" :disabled="!suiteName || !testCases.length || running" style="background:var(--green)">
            {{ running ? 'Running...' : 'Run Now' }}
          </button>
        </div>

        <div v-if="error" class="error-box">{{ error }}</div>
      </div>

      <div class="card">
        <h3>Results</h3>
        <div v-if="results">
          <div class="score-bar">
            <div class="score-fill" :style="{width: (results.score || 0) * 100 + '%', background: results.passed_threshold ? 'var(--green)' : 'var(--red)'}"></div>
            <span class="score-text">{{ results.passed }}/{{ results.total }} passed ({{ Math.round((results.score || 0) * 100) }}%)</span>
          </div>
          <div v-if="results.avg_latency_ms" class="meta">
            Avg latency: {{ Math.round(results.avg_latency_ms) }}ms · Tokens: {{ results.total_tokens }}
          </div>
          <div class="result-list">
            <div v-for="(r, i) in results.results" :key="i" :class="['result-item', r.passed ? 'pass' : 'fail']">
              <div class="result-head">
                <span class="icon">{{ r.passed ? '✅' : '❌' }}</span>
                <span class="prompt-preview">{{ r.prompt }}</span>
              </div>
              <div v-if="r.output" class="output">{{ r.output }}</div>
              <div v-if="r.error" class="output error">{{ r.error }}</div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">Define a suite and click "Run Now" to evaluate.</div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api/client'

const suiteName = ref('')
const testCases = ref([{ prompt: '', expected: '', check: 'contains', max_tokens: 128, temperature: 0 }])
const saving = ref(false)
const running = ref(false)
const error = ref('')
const results = ref(null)

function addCase() {
  testCases.value.push({ prompt: '', expected: '', check: 'contains', max_tokens: 128, temperature: 0 })
}

async function registerSuite() {
  error.value = ''
  saving.value = true
  try {
    await api.post('/api/v1/eval/suites', { name: suiteName.value, test_cases: testCases.value })
    error.value = ''
  } catch (e) {
    error.value = e?.detail || e?.error?.message || 'Failed to register'
  } finally {
    saving.value = false
  }
}

async function runSuite() {
  error.value = ''
  running.value = true
  try {
    await registerSuite()
    results.value = await api.post(`/api/v1/eval/run/${encodeURIComponent(suiteName.value)}`)
  } catch (e) {
    error.value = e?.detail || e?.error?.message || 'Eval failed'
  } finally {
    running.value = false
  }
}
</script>

<style scoped>
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.field { margin-bottom: 10px; }
.field label { display: block; font-size: 10px; color: var(--text2); text-transform: uppercase; margin-bottom: 4px; }
.field input, .field textarea, .field select { width: 100%; padding: 8px 10px; background: var(--surface2); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 12px; }
.field textarea { resize: vertical; min-height: 50px; }
.row { display: flex; gap: 8px; }
.criteria-card { background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 10px; }
.criteria-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.num { font-size: 11px; font-weight: 700; color: var(--accent); }
.remove { background: transparent; border: none; color: var(--red); font-size: 16px; cursor: pointer; }
button { padding: 8px 16px; border-radius: 6px; font-size: 12px; font-weight: 600; border: 1px solid var(--border); background: var(--surface2); color: var(--text); cursor: pointer; }
button.primary { background: var(--accent); color: #fff; border: none; }
button.add { width: 100%; margin-bottom: 12px; }
.actions { display: flex; gap: 8px; margin-top: 12px; }
.err { background: rgba(248,81,73,.1); border: 1px solid rgba(248,81,73,.3); color: var(--red); padding: 8px; border-radius: 6px; margin-top: 10px; font-size: 12px; }
.score-bar { height: 28px; background: var(--surface2); border-radius: 6px; overflow: hidden; position: relative; margin-bottom: 8px; }
.score-fill { height: 100%; transition: width 0.5s; }
.score-text { position: absolute; top: 4px; left: 10px; font-size: 11px; font-weight: 700; color: var(--text); }
.meta { font-size: 11px; color: var(--text2); margin-bottom: 12px; }
.result-item { padding: 10px; border-radius: 6px; margin-bottom: 8px; font-size: 12px; }
.result-item.pass { background: rgba(63,185,80,.08); border: 1px solid rgba(63,185,80,.2); }
.result-item.fail { background: rgba(248,81,73,.08); border: 1px solid rgba(248,81,73,.2); }
.result-head { display: flex; align-items: center; gap: 8px; }
.icon { font-size: 14px; }
.prompt-preview { font-size: 11px; }
.output { margin-top: 6px; padding: 6px; background: var(--surface); border-radius: 4px; font-size: 11px; font-family: monospace; white-space: pre-wrap; }
.empty { padding: 40px; text-align: center; color: var(--text2); font-size: 12px; }
</style>
