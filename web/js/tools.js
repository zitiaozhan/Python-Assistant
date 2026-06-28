/* ===== 工具管理页面 ===== */

async function loadTools() {
    const tools = await apiGet('/tools');
    const container = $('tools-list');
    if (!tools.length) {
        container.innerHTML = '<div class="empty-state">暂无工具</div>';
        return;
    }
    container.innerHTML = tools.map(t => `
        <div class="list-item">
            <div class="info">
                <div class="name">${escapeHtml(t.name)}</div>
                <div class="desc">${escapeHtml(t.description)}</div>
            </div>
        </div>
    `).join('');
}
