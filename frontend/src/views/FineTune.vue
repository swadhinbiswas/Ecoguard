<template>
  <main class="content">
    <div class="page-header"><h2>Fine-Tuning</h2><p>Configure and run LoRA fine-tuning jobs directly.</p></div>
    <div class="split">
      <div class="card">
        <h3>New Fine-Tune Job</h3>
        <div class="field"><label>Base Model</label><input v-model="baseModel" placeholder="/app/models/llama.gguf" /></div>
        <div class="field"><label>Dataset Path</label><input v-model="datasetPath" placeholder="data/dataset.jsonl" /></div>
        <div class="field"><label>Output Directory</label><input v-model="outputDir" placeholder="./models/finetuned" /></div>
        <div class="row">
          <div class="field" style="flex:1"><label>LoRA Rank</label><input v-model.number="rank" type="number" /></div>
          <div class="field" style="flex:1"><label>Epochs</label><input v-model.number="epochs" type="number" /></div>
          <div class="field" style="flex:1"><label>Learning Rate</label><input v-model.number="lr" type="number" step="0.0001" /></div>
        </div>
        <button class="btn btn-primary" @click="startFinetune" :disabled="running">{{ running ? 'Running...' : 'Start Fine-Tuning' }}</button>
        <div v-if="error" class="error-box">{{ error }}</div>
      </div>
      <div class="card">
        <h3>Job Output</h3>
        <div v-if="result" class="result-box">
          <div class="status-badge" :class="result.status">{{ result.status }}</div>
          <div v-if="result.config" class="config-info">
            <div><strong>Model:</strong> {{ result.config.base_model }}</div>
            <div><strong>Rank:</strong> {{ result.config.rank }} | <strong>Epochs:</strong> {{ result.config.epochs }} | <strong>LR:</strong> {{ result.config.learning_rate }}</div>
          </div>
          <div v-if="result.logs" class="log-output">
            <div v-for="(line, i) in result.logs" :key="i" class="log-line">{{ line }}</div>
          </div>
          <div v-if="result.error" class="error-box">{{ result.error }}</div>
        </div>
        <div v-else class="empty-state">Configure a job and click "Start Fine-Tuning" to begin.</div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api/client'

const baseModel = ref('./models/tinyllama.gguf')
const datasetPath = ref('data/dataset.jsonl')
const outputDir = ref('./models/finetuned')
const rank = ref(8)
const epochs = ref(3)
const lr = ref(0.0002)
const running = ref(false)
const error = ref('')
const result = ref(null)

async function startFinetune() {
  error.value = ''
  running.value = true
  try {
    result.value = await api.post('/api/v1/finetune', {
      base_model: baseModel.value, dataset_path: datasetPath.value,
      output_dir: outputDir.value, rank: rank.value, epochs: epochs.value,
      learning_rate: lr.value,
    })
  } catch (e) {
    error.value = e?.detail || e?.error?.message || 'Fine-tuning failed'
  } finally { running.value = false }
}
</script>

<style scoped>
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.field { margin-bottom: 10px; } .row { display: flex; gap: 8px; }
.field label { display: block; font-size: 10px; color: var(--text2); text-transform: uppercase; margin-bottom: 4px; }
.field input { width: 100%; padding: 8px 10px; background: var(--surface2); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 12px; }
button.primary { width: 100%; padding: 10px; background: var(--accent); color: #fff; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; margin-top: 8px; }
button.primary:disabled { opacity: .5; }
.err { background: rgba(248,81,73,.1); border: 1px solid rgba(248,81,73,.3); color: var(--red); padding: 8px; border-radius: 6px; margin-top: 10px; font-size: 12px; }
.result-box { background: var(--surface2); border-radius: 8px; padding: 16px; }
.status-badge { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 11px; font-weight: 700; text-transform: uppercase; margin-bottom: 10px; }
.status-badge.completed { background: rgba(63,185,80,.15); color: var(--green); }
.status-badge.failed { background: rgba(248,81,73,.15); color: var(--red); }
.config-info { font-size: 12px; color: var(--text2); margin-bottom: 10px; }
.config-info div { margin-bottom: 4px; }
.log-output { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 10px; font-family: monospace; font-size: 11px; max-height: 300px; overflow-y: auto; }
.log-line { padding: 2px 0; color: var(--text2); }
.empty { padding: 40px; text-align: center; color: var(--text2); font-size: 12px; }
</style>
