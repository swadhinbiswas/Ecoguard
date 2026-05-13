<template>
  <main class="content">
    <div class="page-header"><h2>Prompt Library</h2><p>Reusable prompt templates — click to use, customize variables.</p></div>
    <div class="tabs"><button :class="{active: tab==='mine'}" @click="tab='mine'">All Templates</button><button :class="{active: tab==='new'}" @click="tab='new'">Create New</button></div>

    <div v-if="tab==='mine'">
      <div class="template-grid">
        <div v-for="t in templates" :key="t.id" class="tpl-card" @click="selected=t">
          <div class="tpl-category">{{ t.category }}</div>
          <div class="tpl-name">{{ t.name }}</div>
          <div class="tpl-desc">{{ t.description }}</div>
          <div class="tpl-tags"><span v-for="tag in t.tags" :key="tag" class="tag">{{ tag }}</span></div>
        </div>
      </div>
      <div v-if="selected" class="tpl-preview">
        <h4>{{ selected.name }}</h4>
        <pre class="code">{{ selected.template }}</pre>
        <div class="preview-vars" v-if="selected.variables">
          <div v-for="v in selected.variables" :key="v" class="field" style="display:inline-block;margin:4px 8px 4px 0">
            <label>{{ v }}</label><input :placeholder="v" size="16" />
          </div>
        </div>
        <div class="actions"><button @click="selected=null">Close</button><button class="seed" @click="seedBuiltins">Seed Built-ins</button></div>
      </div>
      <button v-if="!templates.length" class="seed" @click="seedBuiltins">Load Built-in Templates</button>
    </div>

    <div v-if="tab==='new'" class="card">
      <div class="field"><label>Name</label><input v-model="newTpl.name" /></div>
      <div class="field"><label>Category</label><input v-model="newTpl.category" placeholder="custom" /></div>
      <div class="field"><label>Description</label><input v-model="newTpl.description" /></div>
      <div class="field"><label>Template</label><textarea v-model="newTpl.template" rows="4" placeholder="Use {variable} placeholders" /></div>
      <div class="field"><label>Variables (comma-separated)</label><input v-model="newTpl.varsStr" placeholder="text, tone, audience" /></div>
      <div class="field"><label>Tags (comma-separated)</label><input v-model="newTpl.tagsStr" placeholder="code, review" /></div>
      <button class="btn btn-primary" @click="createTemplate" :disabled="creating">{{ creating?'Creating...':'Save Template' }}</button>
    </div>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client'

const tab = ref('mine')
const templates = ref([])
const selected = ref(null)
const creating = ref(false)
const newTpl = ref({ name:'', category:'custom', description:'', template:'', varsStr:'', tagsStr:'' })

async function load() { templates.value = (await api.get('/api/v1/templates')).templates }
async function seedBuiltins() { await api.post('/api/v1/templates/seed'); await load() }
async function createTemplate() {
  creating.value = true
  try {
    await api.post('/api/v1/templates', {
      ...newTpl.value,
      variables: newTpl.value.varsStr.split(',').map(s=>s.trim()).filter(Boolean),
      tags: newTpl.value.tagsStr.split(',').map(s=>s.trim()).filter(Boolean),
    })
    newTpl.value = { name:'', category:'custom', description:'', template:'', varsStr:'', tagsStr:'' }
    tab.value = 'mine'
    await load()
  } catch(e) {} finally { creating.value = false }
}
onMounted(load)
</script>

<style scoped>
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tabs button { padding: 8px 16px; border: 1px solid var(--border); background: var(--surface2); color: var(--text2); border-radius: 6px; cursor: pointer; font-size: 12px; }
.tabs button.active { background: var(--accent); color: #fff; }
.template-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.tpl-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px; cursor: pointer; transition: .15s; }
.tpl-card:hover { border-color: var(--accent); }
.tpl-category { font-size: 10px; color: var(--accent); text-transform: uppercase; margin-bottom: 4px; }
.tpl-name { font-size: 14px; font-weight: 700; margin-bottom: 4px; }
.tpl-desc { font-size: 11px; color: var(--text2); margin-bottom: 8px; }
.tpl-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.tag { font-size: 10px; padding: 2px 6px; background: var(--surface2); border-radius: 4px; color: var(--text2); }
.tpl-preview { margin-top: 16px; background: var(--surface); border: 1px solid var(--accent); border-radius: 10px; padding: 16px; }
.code { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 12px; font-size: 12px; white-space: pre-wrap; font-family: monospace; }
.actions { display: flex; gap: 8px; margin-top: 8px; }
button { padding: 8px 16px; border-radius: 6px; font-size: 12px; border: 1px solid var(--border); background: var(--surface2); color: var(--text); cursor: pointer; }
button.primary { background: var(--accent); color: #fff; border: none; } button.seed { background: var(--green); color: #fff; border: none; margin-top: 12px; width: 100%; }
.field { margin-bottom: 10px; } .field label { display: block; font-size: 10px; color: var(--text2); text-transform: uppercase; margin-bottom: 4px; }
.field input, .field textarea { width: 100%; padding: 8px 10px; background: var(--surface2); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 12px; }
</style>
