<template>
  <main class="content">
    <div class="page-header">
      <h2>Platform Overview</h2>
      <p>Real-time monitoring of your LLM inference platform</p>
    </div>
    <section v-if="system.demo_mode" class="hero demo">
      <div>
        <span class="eyebrow">Demo workspace</span>
        <h3>Explore Eco-Guard safely</h3>
        <p>This public demo is read-only. You can inspect health, registry, jobs, datasets, and monitoring flows without changing production state.</p>
      </div>
      <router-link to="/models" class="hero-action">View model registry</router-link>
    </section>
    <section v-else-if="system.first_run" class="hero setup">
      <div>
        <span class="eyebrow">Self-host setup</span>
        <h3>Finish production readiness</h3>
        <p>Complete these checks before sharing this instance with a team.</p>
      </div>
      <ul>
        <li v-for="item in system.setup_required" :key="item">{{ item }}</li>
      </ul>
    </section>
    <div class="stats-grid">
      <div class="stat" v-for="s in stats" :key="s.label">
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-value" :style="{ color: s.color }">{{ s.value }}</div>
        <div class="stat-sub">{{ s.sub }}</div>
      </div>
    </div>
    <section class="onboarding">
      <div class="step" v-for="step in steps" :key="step.title">
        <div class="step-num">{{ step.num }}</div>
        <h4>{{ step.title }}</h4>
        <p>{{ step.text }}</p>
      </div>
    </section>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client'

const stats = ref([])
const system = ref({ demo_mode: false, first_run: false, setup_required: [] })
const steps = [
  { num: '01', title: 'Connect a model backend', text: 'Use llama.cpp locally or point Eco-Guard at Ollama, vLLM, TGI, or an OpenAI-compatible endpoint.' },
  { num: '02', title: 'Create API access', text: 'Issue scoped keys for apps and users, then track requests, tokens, latency, and errors by owner.' },
  { num: '03', title: 'Operate deployments', text: 'Register versions, promote candidates, monitor drift, evaluate quality, and roll back when needed.' },
]

onMounted(async () => {
  try {
    system.value = await api.get('/api/v1/system/status')
    const h = await api.get('/api/v1/health')
    const s = await api.get('/api/v1/metrics/summary')
    stats.value = [
      { label: 'Database', value: h.checks?.database === 'up' ? 'Connected' : 'Down', color: h.checks?.database === 'up' ? 'var(--green)' : 'var(--red)', sub: '' },
      { label: 'Model', value: s.model_loaded ? 'Loaded' : 'Offline', color: s.model_loaded ? 'var(--green)' : 'var(--red)', sub: '' },
      { label: 'Rate Limiting', value: s.rate_limit_enabled ? 'Active' : 'Off', color: s.rate_limit_enabled ? 'var(--accent)' : 'var(--text2)', sub: '' },
      { label: 'Cache', value: `${s.cache_size} entries`, color: 'var(--accent)', sub: s.cache_enabled ? 'Enabled' : 'Disabled' },
      { label: 'Drift Samples', value: s.drift_samples, color: 'var(--purple)', sub: 'In window' },
      { label: 'Version', value: h.version || '—', color: 'var(--text)', sub: h.service || '' },
      { label: 'Mode', value: system.value.demo_mode ? 'Demo' : system.value.environment, color: system.value.demo_mode ? 'var(--yellow)' : 'var(--text)', sub: system.value.demo_read_only ? 'Read-only' : 'Self-hosted' },
    ]
  } catch {}
})
</script>

<style scoped>
.content { flex: 1; padding: 28px 32px; overflow-y: auto; }
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 22px; font-weight: 700; }
.page-header p { color: var(--text2); font-size: 13px; margin-top: 2px; }
.hero { display: flex; justify-content: space-between; gap: 24px; align-items: center; border: 1px solid var(--border); border-radius: 18px; padding: 22px; margin-bottom: 18px; background: linear-gradient(135deg, rgba(77,166,255,.14), rgba(20,27,34,.8)); }
.hero.setup { background: linear-gradient(135deg, rgba(210,153,34,.14), rgba(20,27,34,.8)); align-items: flex-start; }
.hero h3 { font-size: 22px; margin: 3px 0 6px; }
.hero p { color: var(--text2); max-width: 620px; }
.hero ul { color: var(--text2); padding-left: 18px; min-width: 320px; }
.hero-action { white-space: nowrap; border-radius: 10px; background: var(--accent); color: white; padding: 10px 14px; font-weight: 700; }
.eyebrow { color: var(--accent); text-transform: uppercase; font-size: 11px; letter-spacing: .8px; font-weight: 800; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }
.stat { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px 20px; }
.stat-label { font-size: 11px; color: var(--text2); text-transform: uppercase; letter-spacing: .5px; }
.stat-value { font-size: 26px; font-weight: 700; margin: 4px 0; }
.stat-sub { font-size: 12px; color: var(--text2); }
.onboarding { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 18px; }
.step { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 18px; }
.step-num { color: var(--accent); font-weight: 800; font-size: 12px; margin-bottom: 10px; }
.step h4 { font-size: 15px; margin-bottom: 6px; }
.step p { color: var(--text2); font-size: 13px; }
@media (max-width: 900px) {
  .hero { display: block; }
  .hero-action { display: inline-block; margin-top: 14px; }
  .onboarding { grid-template-columns: 1fr; }
}
</style>
