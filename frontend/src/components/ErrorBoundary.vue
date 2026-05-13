<template>
  <div v-if="error" class="error-boundary">
    <h4>Something went wrong</h4>
    <p>{{ error.message }}</p>
    <button @click="reset">Try Again</button>
  </div>
  <slot v-else />
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'

const error = ref(null)

onErrorCaptured((err) => { error.value = err; return false })

function reset() { error.value = null }
</script>

<style scoped>
.error-boundary { padding: 24px; margin: 16px; background: rgba(248,81,73,.08); border: 1px solid rgba(248,81,73,.3); border-radius: 12px; text-align: center; }
.error-boundary h4 { color: var(--red); margin-bottom: 8px; }
.error-boundary p { font-size: 12px; color: var(--text2); margin-bottom: 12px; }
button { padding: 8px 16px; background: var(--accent); color: #fff; border: none; border-radius: 6px; cursor: pointer; }
</style>
