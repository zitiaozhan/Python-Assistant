/* ===== 页面路由 + 应用初始化 ===== */

let currentPage = 'chat';

function switchPage(page) {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    const navItem = document.querySelector(`.nav-item[data-page="${page}"]`);
    if (navItem) navItem.classList.add('active');

    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const pageEl = $(`page-${page}`);
    if (pageEl) pageEl.classList.add('active');

    currentPage = page;

    if (page === 'config')    loadConfig();
    if (page === 'tools')     loadTools();
    if (page === 'skills')    loadSkills();
    if (page === 'blacklist') loadBlacklist();
}

function initNav() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => switchPage(item.dataset.page));
    });
}

/* ===== QR 码弹窗 ===== */
let serverInfo = null;

async function initQRCode() {
    const btn = $('btn-qrcode');
    const modal = $('qr-modal');
    const closeBtn = $('btn-qr-close');
    const copyBtn = $('btn-qr-copy');
    const urlEl = $('qr-url');
    if (!btn || !modal) return;

    // 获取服务器信息
    try {
        serverInfo = await apiGet('/server-info');
        if (urlEl && serverInfo.mobile_url) {
            urlEl.textContent = serverInfo.mobile_url;
            urlEl.href = serverInfo.mobile_url;
        }
    } catch (e) {
        console.warn('Failed to get server info', e);
    }

    btn.addEventListener('click', () => {
        modal.classList.add('active');
        // 刷新 QR 图片
        const img = $('qr-image');
        if (img) img.src = `/api/qrcode.svg?t=${Date.now()}`;
    });

    closeBtn && closeBtn.addEventListener('click', () => modal.classList.remove('active'));

    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
    });

    copyBtn && copyBtn.addEventListener('click', async () => {
        const url = serverInfo?.mobile_url || urlEl?.textContent;
        if (!url) return;
        try {
            await navigator.clipboard.writeText(url);
            showToast('链接已复制', 'success');
        } catch {
            showToast('请手动复制链接', 'info');
        }
    });

    urlEl && urlEl.addEventListener('click', async (e) => {
        e.preventDefault();
        const url = urlEl.href || urlEl.textContent;
        try {
            await navigator.clipboard.writeText(url);
            showToast('链接已复制', 'success');
        } catch { /* ignore */ }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') modal.classList.remove('active');
    });
}

/* ===== 启动 ===== */
document.addEventListener('DOMContentLoaded', async () => {
    initNav();
    initChat();
    initConfig();
    initBlacklist();
    initSkills();
    await initQRCode();

    connectWS();
    loadConfig();
    loadSkills();
});
