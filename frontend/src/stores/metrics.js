import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const WS_URL = (import.meta.env.VITE_WS_URL || '').replace(/^http/, 'ws') || `ws://${window.location.host}/ws/metrics`

export const useMetricsStore = defineStore('metrics', () => {
  const connected = ref(false)
  const modelLoaded = ref(false)
  const concurrency = ref({ max: 4, in_use: 0 })
  const latency = ref({ recent: [] })
  const drift = ref({ samples: 0 })
  const requestRate = ref(0)
  const lastUpdate = ref(0)
  const errorCount = ref(0)
  const uptime = ref('')

  const avgLatency = computed(() => {
    const arr = latency.value.recent
    return arr.length ? Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) : 0
  })

  const utilizationPct = computed(() => {
    const { max, in_use } = concurrency.value
    return max ? Math.round((in_use / max) * 100) : 0
  })

  let ws = null
  let reconnectTimer = null
  let startTime = Date.now()
  let lastCount = 0

  function connect() {
    if (ws && ws.readyState === WebSocket.OPEN) return

    try {
      ws = new WebSocket(WS_URL)
      ws.onopen = () => {
        connected.value = true
        errorCount.value = 0
        startTime = Date.now()
        updateUptime()
      }
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          modelLoaded.value = data.model_loaded ?? modelLoaded.value
          concurrency.value = data.concurrency ?? concurrency.value
          latency.value = data.latency ?? latency.value
          drift.value = data.drift ?? drift.value
          lastUpdate.value = data.timestamp || Date.now()

          const now = Date.now()
          const elapsed = (now - (lastCount ? lastCount : now)) / 1000
          if (data.latency?.recent) {
            requestRate.value = elapsed > 0 ? Math.round(data.latency.recent.length / elapsed) : 0
          }
          lastCount = Date.now()
          updateUptime()
        } catch {}
      }
      ws.onclose = () => { connected.value = false; scheduleReconnect() }
      ws.onerror = () => { errorCount.value++; ws?.close() }
    } catch {
      scheduleReconnect()
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    reconnectTimer = setTimeout(connect, 3000)
  }

  function updateUptime() {
    const sec = Math.floor((Date.now() - startTime) / 1000)
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    const s = sec % 60
    uptime.value = `${h}h ${m}m ${s}s`
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
    ws = null
    connected.value = false
  }

  return {
    connected, modelLoaded, concurrency, latency, drift,
    requestRate, lastUpdate, errorCount, uptime,
    avgLatency, utilizationPct, connect, disconnect,
  }
})
