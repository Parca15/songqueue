/**
 * SongQueue - JavaScript compartido
 * Maneja WebSockets, fingerprints, y renderizado de cola.
 */

// ── Device Fingerprint ──
async function generateFingerprint() {
    const components = [
        navigator.userAgent,
        navigator.language,
        screen.width + 'x' + screen.height,
        screen.colorDepth,
        new Date().getTimezoneOffset(),
        !!window.sessionStorage,
        !!window.localStorage,
        navigator.hardwareConcurrency || 'unknown',
    ];

    // Canvas fingerprint
    try {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        ctx.textBaseline = 'top';
        ctx.font = '14px Arial';
        ctx.fillText('SongQueue fingerprint', 2, 2);
        components.push(canvas.toDataURL());
    } catch (e) { components.push('no-canvas'); }

    const str = components.join('###');
    const hash = await sha256(str);
    return hash;
}

async function sha256(str) {
    const buf = new TextEncoder().encode(str);
    const hash = await crypto.subtle.digest('SHA-256', buf);
    return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ── WebSocket ──
let WS_CONNECTION = null;
let WS_RECONNECT_INTERVAL = 3000;

function connectWebSocket(venueId, role, deviceId) {
    if (WS_CONNECTION) {
        WS_CONNECTION.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/venue/${venueId}`);
    WS_CONNECTION = ws;

    ws.onopen = () => {
        console.log(`[WS] Connected to venue ${venueId} as ${role}`);
        ws.send(JSON.stringify({ action: 'register', role, device_id: deviceId }));

        // Ping cada 30s para mantener vivo
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: 'ping', timestamp: Date.now() }));
            }
        }, 30000);
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleWebSocketMessage(msg, venueId);
    };

    ws.onclose = () => {
        console.log('[WS] Disconnected, reconnecting...');
        setTimeout(() => connectWebSocket(venueId, role, deviceId), WS_RECONNECT_INTERVAL);
    };

    ws.onerror = (err) => {
        console.error('[WS] Error:', err);
    };
}

function handleWebSocketMessage(msg, venueId) {
    if (msg.type === 'queue_updated') {
        renderQueue(msg.data);
    }
    if (msg.type === 'now_playing') {
        renderNowPlaying(msg.data);
    }
    if (msg.type === 'registered') {
        console.log('[WS] Registered:', msg);
    }
    if (msg.type === 'stats') {
        updateStats(msg);
    }
}

// ── Queue Rendering ──
async function loadQueue(venueId, isAdmin = false) {
    try {
        const resp = await fetch(`/api/v1/queue/venue/${venueId}`);
        const data = await resp.json();
        renderQueue(data, isAdmin);
    } catch (e) {
        console.error('Error loading queue:', e);
    }
}

function renderQueue(data, isAdmin = false) {
    const nowPlayingEl = document.getElementById(isAdmin ? 'admin-now-playing' : 'now-playing');
    const queueListEl = document.getElementById(isAdmin ? 'admin-queue-list' : 'queue-list');
    const emptyEl = document.getElementById('queue-empty');
    const statTotal = document.getElementById('stat-total');
    const statLimit = document.getElementById('stat-limit');

    // Now playing
    if (nowPlayingEl) {
        if (data.now_playing && data.now_playing.song) {
            const song = data.now_playing.song;
            nowPlayingEl.innerHTML = `
                <h3>▶️ Sonando ahora</h3>
                <div class="song-title">${escapeHtml(song.title)}</div>
                <div class="song-channel">${escapeHtml(song.channel || 'YouTube')}</div>
                ${data.now_playing.requested_by ? `<small>Solicitada por: ${escapeHtml(data.now_playing.requested_by)}</small>` : ''}
            `;
        } else {
            nowPlayingEl.innerHTML = '<div class="empty-msg">Nada sonando ahora</div>';
        }
    }

    // Queue list
    if (queueListEl) {
        if (data.upcoming && data.upcoming.length > 0) {
            queueListEl.innerHTML = data.upcoming.map((item, idx) => {
                const song = item.song || {};
                const adminButtons = isAdmin ? `
                    <div class="actions">
                        <button class="btn btn-primary" onclick="playItem(${item.id})">▶️</button>
                        <button class="btn btn-danger" onclick="removeItem(${item.id})">🗑️</button>
                    </div>
                ` : '';
                return `
                    <li data-id="${item.id}">
                        <span class="pos">${idx + 1}</span>
                        <img class="thumb" src="${song.thumbnail_url || ''}" alt="">
                        <div class="info">
                            <div class="title">${escapeHtml(song.title || 'Sin título')}</div>
                            <div class="meta">${escapeHtml(song.channel || 'YouTube')} ${item.requested_by ? '• ' + escapeHtml(item.requested_by) : ''}</div>
                        </div>
                        ${adminButtons}
                    </li>
                `;
            }).join('');
            if (emptyEl) emptyEl.style.display = 'none';
        } else {
            queueListEl.innerHTML = '';
            if (emptyEl) emptyEl.style.display = 'block';
        }
    }

    // Stats
    if (statTotal) statTotal.textContent = data.total_pending || 0;
    if (statLimit && window.CURRENT_VENUE) statLimit.textContent = window.CURRENT_VENUE.max_songs_per_device;
}

function renderNowPlaying(item) {
    const el = document.getElementById('now-playing');
    if (!el || !item || !item.song) return;
    const song = item.song;
    el.innerHTML = `
        <h3>▶️ Sonando ahora</h3>
        <div class="song-title">${escapeHtml(song.title)}</div>
        <div class="song-channel">${escapeHtml(song.channel || 'YouTube')}</div>
    `;
}

function updateStats(msg) {
    const el = document.getElementById('stat-connections');
    if (el) el.textContent = msg.total_connections || 0;
    const wsText = document.getElementById('ws-text');
    const wsInd = document.getElementById('ws-indicator');
    if (wsText) wsText.textContent = `WebSocket: ${msg.total_connections} conectados`;
    if (wsInd) wsInd.className = 'indicator online';
}

// Admin helpers (globales)
window.playItem = async function(itemId) {
    const venueId = window.ADMIN_VENUE?.venue_id;
    if (!venueId) return;
    await fetch(`/api/v1/queue/venue/${venueId}/play/${itemId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${window.ADMIN_TOKEN}` },
    });
};

window.removeItem = async function(itemId) {
    const venueId = window.ADMIN_VENUE?.venue_id;
    if (!venueId) return;
    await fetch(`/api/v1/queue/venue/${venueId}/item/${itemId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${window.ADMIN_TOKEN}` },
    });
    loadQueue(venueId, true);
};
