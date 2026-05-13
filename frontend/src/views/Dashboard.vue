<template>
  <main class="content">
    <div class="page-header">
      <h2>Platform Overview</h2>
      <p>Real-time monitoring of your LLM inference platform</p>
    </div>

    <section v-if="system.demo_mode" class="banner banner-blue">
      <div class="banner-icon">🔒</div>
      <div><strong>Demo workspace</strong><p>Read-only mode — explore safely without changing production state.</p></div>
    </section>

    <section v-else-if="system.first_run && system.setup_required?.length" class="banner banner-yellow">
      <div class="banner-icon">⚡</div>
      <div>
        <strong>Finish setup</strong>
        <ul v-if="system.setup_required?.length"><li v-for="item in system.setup_required" :key="item">{{ item }}</li></ul></div>
    </section>

    <div class="stats-grid">
      <div class="stat-card" v-for="s in stats" :key="s.label">
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-value" :style="{color: s.color}">{{ s.value }}</div>
        <div class="stat-sub">{{ s.sub }}</div>
      </div>
    </div>

    <div class="card" style="margin-top: 20px;">
      <h3>Getting Started</h3>
      <div class="steps">
        <div class="step" v-for="step in steps" :key="step.num">
          <div class="step-badge">{{ step.num }}</div>
          <div>
            <h4>{{ step.title }}</h4>
            <p>{{ step.text }}</p>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client'

const stats = ref([])
const system = ref({ demo_mode: false, first_run: false, setup_required: [] })
const steps = [
  { num: 1, title: 'Connect a model backend', text: 'Use llama.cpp locally or point at Ollama, vLLM, TGI, or any OpenAI-compatible endpoint.' },
  { num: 2, title: 'Create API access', text: 'Issue scoped keys for apps and users. Track requests, tokens, latency, and drift by owner.' },
  { num: 3, title: 'Operate deployments', text: 'Register versions, promote candidates, monitor drift, evaluate quality, and roll back when needed.' },
]

onMounted(async () => {
  try {
    system.value = await api.get('/api/v1/system/status')
    const h = await api.get('/api/v1/health')
    const s = await api.get('/api/v1/metrics/summary')
    stats.value = [
      { label: 'Database', value: h.checks?.database === 'up' ? 'Connected' : 'Down', color: h.checks?.database === 'up' ? 'var(--green)' : 'var(--red)', sub: '' },
      { label: 'Model', value: s.model_loaded ? 'Loaded' : 'Offline', color: s.model_loaded ? 'var(--green)' : 'var(--red)', sub: s.model_loaded ? 'Ready' : 'No model' },
      { label: 'Rate Limiting', value: s.rate_limit_enabled ? 'Active' : 'Off', color: s.rate_limit_enabled ? 'var(--accent)' : 'var(--text2)', sub: '' },
      { label: 'Cache', value: `${s.cache_size} entries`, color: 'var(--accent)', sub: s.cache_enabled ? 'Enabled' : 'Disabled' },
      { label: 'Drift', value: s.drift_samples ?? 0, color: 'var(--purple)', sub: 'Samples tracked' },
      { label: 'Version', value: h.version || '—', color: 'var(--text)', sub: h.service || '' },
      { label: 'Environment', value: system.value.demo_mode ? 'Demo' : h.environment || system.value.environment, color: system.value.demo_mode ? 'var(--yellow)' : 'var(--text)', sub: system.value.demo_read_only ? 'Read-only' : 'Development' },
    ]
  } catch {}
})
</script>

<style scoped>
.banner { display: flex; align-items: flex-start; gap: 14px; border-radius: var(--radius); padding: 16px 20px; margin-bottom: 22px; }
.banner-blue { background: rgba(59,130,246,.08); border: 1px solid rgba(59,130,246,.2); }
.banner-yellow { background: rgba(234,179,8,.08); border: 1px solid rgba(234,179,8,.2); }
.banner-icon { font-size: 20px; flex-shrink: 0; }
.banner strong { font-size: 14px; margin-bottom: 4px; display: block; }
.banner p, .banner li { font-size: 13px; color: var(--text2); }
.banner ul { padding-left: 18px; margin-top: 4px; }

.steps { display: flex; flex-direction: column; gap: 16px; }
.step { display: flex; gap: 16px; align-items: flex-start; padding: 14px; background: var(--surface2); border-radius: 8px; }
.step-badge { width: 32px; height: 32px; border-radius: 8px; background: var(--accent); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; flex-shrink: 0; }
.step h4 { font-size: 14px; font-weight: 600; margin-bottom: 2px; }
.step p { font-size: 12px; color: var(--text2); }
</style>
