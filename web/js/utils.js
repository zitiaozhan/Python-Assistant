/* ===== 通用工具函数 ===== */

function $(id) { return document.getElementById(id); }

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info', duration = 3000) {
    const container = $('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="toast-icon">${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span><span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    setTimeout(() => { toast.classList.add('fade-out'); setTimeout(() => toast.remove(), 300); }, duration);
}

/* ===== Markdown 渲染（聊天消息 + 技能编辑器共用）===== */

function renderMarkdown(text) {
    if (!text) return '';

    // ── 步骤 1：保护代码块（替换为占位符）──────────────────────────────
    const codeBlocks = [];
    text = text.replace(/```([\w]*)\n?([\s\S]*?)```/g, (_, lang, code) => {
        const idx = codeBlocks.length;
        codeBlocks.push({ lang: lang.trim(), code: code.replace(/\n$/, '') });
        return `\x00CODE${idx}\x00`;
    });

    // 行内代码也保护
    const inlineCodes = [];
    text = text.replace(/`([^`\n]+)`/g, (_, code) => {
        const idx = inlineCodes.length;
        inlineCodes.push(code);
        return `\x00IC${idx}\x00`;
    });

    // ── 步骤 2：HTML 转义（保留占位符）──────────────────────────────────
    // 手动转义，跳过占位符
    text = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');

    // ── 步骤 3：行级规则（逐行处理）─────────────────────────────────────
    const lines = text.split('\n');
    const out = [];
    let inUl = false, inOl = false, inBlockquote = false;

    const flushList = () => {
        if (inUl) { out.push('</ul>'); inUl = false; }
        if (inOl) { out.push('</ol>'); inOl = false; }
    };
    const flushBq = () => {
        if (inBlockquote) { out.push('</blockquote>'); inBlockquote = false; }
    };

    for (let i = 0; i < lines.length; i++) {
        let line = lines[i];

        // 水平线
        if (/^---+$|^\*\*\*+$|^___+$/.test(line.trim())) {
            flushList(); flushBq();
            out.push('<hr>'); continue;
        }

        // 标题
        const hm = line.match(/^(#{1,6})\s+(.*)/);
        if (hm) {
            flushList(); flushBq();
            const level = hm[1].length;
            out.push(`<h${level}>${_inline(hm[2])}</h${level}>`);
            continue;
        }

        // 引用块
        const bqm = line.match(/^&gt;\s?(.*)/);
        if (bqm) {
            if (!inBlockquote) { flushList(); out.push('<blockquote>'); inBlockquote = true; }
            out.push(`<p>${_inline(bqm[1])}</p>`);
            continue;
        } else if (inBlockquote && line.trim() === '') {
            flushBq();
        } else {
            flushBq();
        }

        // 无序列表
        const ulm = line.match(/^(\s*)[-*+]\s+(.*)/);
        if (ulm) {
            if (!inUl) { flushList(); out.push('<ul>'); inUl = true; }
            out.push(`<li>${_inline(ulm[2])}</li>`);
            continue;
        }

        // 有序列表
        const olm = line.match(/^(\s*)\d+\.\s+(.*)/);
        if (olm) {
            if (!inOl) { flushList(); out.push('<ol>'); inOl = true; }
            out.push(`<li>${_inline(olm[2])}</li>`);
            continue;
        }

        // 普通行
        flushList();

        if (line.trim() === '') {
            out.push('<br>');
        } else {
            out.push(`<p>${_inline(line)}</p>`);
        }
    }

    flushList(); flushBq();

    let html = out.join('\n');

    // ── 步骤 4：还原行内代码 ─────────────────────────────────────────────
    html = html.replace(/\x00IC(\d+)\x00/g, (_, i) =>
        `<code>${escapeHtml(inlineCodes[+i])}</code>`
    );

    // ── 步骤 5：还原代码块 ────────────────────────────────────────────────
    html = html.replace(/\x00CODE(\d+)\x00/g, (_, i) => {
        const { lang, code } = codeBlocks[+i];
        return `<pre><code class="language-${escapeHtml(lang)}">${escapeHtml(code)}</code></pre>`;
    });

    return html;
}

/** 处理行内 markdown（粗体、斜体、链接、图片） */
function _inline(text) {
    // 粗体+斜体
    text = text.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    text = text.replace(/\_\_\_(.*?)\_\_\_/g, '<strong><em>$1</em></strong>');
    text = text.replace(/\_\_(.*?)\_\_/g, '<strong>$1</strong>');
    // 删除线
    text = text.replace(/~~(.*?)~~/g, '<del>$1</del>');
    // 图片（先于链接）
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2" style="max-width:100%;border-radius:8px;">');
    // 链接
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return text;
}
