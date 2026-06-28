/* ===== 黑名单管理页面 ===== */

async function loadBlacklist() {
    const rules = await apiGet('/blacklist');
    const container = $('blacklist-list');
    if (!rules.length) {
        container.innerHTML = '<div class="empty-state">暂无黑名单规则</div>';
        return;
    }
    container.innerHTML = rules.map(r => `
        <div class="list-item">
            <div class="info">
                <div class="name" style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;">${escapeHtml(r)}</div>
            </div>
            <div class="actions">
                <button class="danger" onclick="removeBlacklist('${escapeHtml(r)}')">删除</button>
            </div>
        </div>
    `).join('');
}

window.removeBlacklist = async function(rule) {
    const res = await apiDelete('/blacklist', { rule });
    if (res.error) { showToast(res.error, 'error'); }
    else { showToast('已删除', 'success'); loadBlacklist(); }
};

function initBlacklist() {
    $('btn-add-blacklist').addEventListener('click', async () => {
        const rule = $('new-blacklist-rule').value.trim();
        if (!rule) { showToast('规则不能为空', 'error'); return; }
        const res = await apiPost('/blacklist', { rule });
        if (res.error) { showToast(res.error, 'error'); }
        else {
            showToast('已添加', 'success');
            $('new-blacklist-rule').value = '';
            loadBlacklist();
        }
    });
}
