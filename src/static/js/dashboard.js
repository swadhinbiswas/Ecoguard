// Live WebSocket metrics
class LiveMetrics {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.reconnectDelay = 2000;
        this.listeners = {};
    }

    connect() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${location.host}${this.url}`);

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.emit('metrics', data);
            } catch(e) {}
        };

        this.ws.onclose = () => {
            setTimeout(() => this.connect(), this.reconnectDelay);
        };

        this.ws.onerror = () => {};
    }

    on(event, cb) { this.listeners[event] = cb; }
    emit(event, data) { if (this.listeners[event]) this.listeners[event](data); }
    close() { if (this.ws) this.ws.close(); }
}

// Toast notifications
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast alert alert-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// Format numbers
function fmt(n, decimals = 1) {
    if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n/1e3).toFixed(1) + 'K';
    return n.toFixed(decimals);
}

// Relative time
function timeAgo(dateStr) {
    const d = new Date(dateStr);
    const now = new Date();
    const s = Math.floor((now - d) / 1000);
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s/60) + 'm ago';
    if (s < 86400) return Math.floor(s/3600) + 'h ago';
    return Math.floor(s/86400) + 'd ago';
}
