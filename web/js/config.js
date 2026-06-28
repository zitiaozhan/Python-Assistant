/* ===== 模型配置页面 ===== */

async function loadConfig() {
    const cfg = await apiGet('/config');
    if (cfg.error) { showToast(cfg.error, 'error'); return; }
    $('cfg-base-url').value    = cfg.base_url || '';
    $('cfg-api-key').value     = cfg.api_key || '';
    $('cfg-model').value       = cfg.model || '';
    $('cfg-temperature').value = cfg.temperature ?? 0.7;
    $('cfg-max-tokens').value  = cfg.max_tokens ?? 2048;
    $('cfg-stream').value      = String(cfg.stream ?? true);
    $('cfg-system-prompt').value = cfg.system_prompt || '';
    // 更新聊天头部的模型名称
    const modelNameEl = $('model-name');
    if (modelNameEl && cfg.model) modelNameEl.textContent = cfg.model;
}

function initConfig() {
    $('btn-save-config').addEventListener('click', async () => {
        const payload = {
            base_url:      $('cfg-base-url').value,
            api_key:       $('cfg-api-key').value,
            model:         $('cfg-model').value,
            temperature:   parseFloat($('cfg-temperature').value),
            max_tokens:    parseInt($('cfg-max-tokens').value),
            stream:        $('cfg-stream').value === 'true',
            system_prompt: $('cfg-system-prompt').value,
        };
        const res = await apiPost('/config', payload);
        if (res.error) { showToast(res.error, 'error'); }
        else { showToast('配置已保存', 'success'); }
    });
}
