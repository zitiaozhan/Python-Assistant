/* ===== API 请求封装 ===== */

const API_BASE = '';

async function apiGet(path) {
    const res = await fetch(`${API_BASE}/api${path}`);
    return res.json();
}

async function apiPost(path, body) {
    const res = await fetch(`${API_BASE}/api${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return res.json();
}

async function apiPut(path, body) {
    const res = await fetch(`${API_BASE}/api${path}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return res.json();
}

async function apiDelete(path, body) {
    const res = await fetch(`${API_BASE}/api${path}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
    });
    return res.json();
}
