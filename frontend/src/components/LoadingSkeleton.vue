<template>
  <div class="skeleton">
    <div class="skeleton-header"><div class="sk-line sk-w60"></div><div class="sk-line sk-w30"></div></div>
    <div class="skeleton-body">
      <div class="sk-card"><div class="sk-line sk-w80"></div><div class="sk-line sk-w50"></div><div class="sk-line sk-w90"></div></div>
      <div class="sk-card"><div class="sk-line sk-w80"></div><div class="sk-line sk-w50"></div><div class="sk-line sk-w90"></div></div>
      <div class="sk-card"><div class="sk-line sk-w80"></div><div class="sk-line sk-w50"></div><div class="sk-line sk-w90"></div></div>
    </div>
  </div>
</template>

<style scoped>
.skeleton { padding: 16px; }
.skeleton-header { margin-bottom: 20px; }
.skeleton-body { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.sk-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px; }
.sk-line { height: 12px; background: var(--surface2); border-radius: 4px; margin-bottom: 8px; animation: pulse 1.5s infinite; }
.sk-w60 { width: 60%; } .sk-w30 { width: 30%; } .sk-w80 { width: 80%; } .sk-w50 { width: 50%; } .sk-w90 { width: 90%; }
@keyframes pulse { 0%, 100% { opacity: .4; } 50% { opacity: .8; } }
</style>
