/* ===== 对话 WebSocket + 消息管理（广播架构） ===== */

let ws = null;
let isStreaming = false;
let pendingConfirm = null;
let msgCount = 0;

// 回放时缓存 tool_call（没有 start 事件，需要等 assistant_message 一起渲染）
let _pendingToolCalls = [];

/* ─── WebSocket 连接 ─────────────────────────────── */
function connectWS() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws/chat`);

    ws.onopen = () => {
        $('model-name').textContent = '已连接';
        setConnectionStatus(true);
    };
    ws.onmessage = (event) => handleWSMessage(JSON.parse(event.data));
    ws.onclose = () => {
        setConnectionStatus(false);
        $('model-name').textContent = '已断开';
        setTimeout(connectWS, 3000);
    };
    ws.onerror = () => {
        setConnectionStatus(false);
        $('model-name').textContent = '连接错误';
    };
}

function setConnectionStatus(connected) {
    const dot = document.querySelector('.status-dot');
    if (!dot) return;
    dot.style.background   = connected ? 'var(--success)' : 'var(--danger)';
    dot.style.boxShadow    = connected ? '0 0 0 3px var(--success-soft)' : '0 0 0 3px var(--danger-soft)';
}

/* ─── 消息路由 ───────────────────────────────────── */
function handleWSMessage(msg) {
    switch (msg.type) {

        /* == 实时流式事件 == */
        case 'user_message':
            // 广播来的用户消息：本机已显示则去重
            if (!_isSelf(msg.content)) addUserMessage(msg.content);
            break;

        case 'start':
            isStreaming = true;
            _createStreamingBubble();
            break;

        case 'chunk':
            _appendChunk(msg.content);
            break;

        case 'tool_call':
            if (isStreaming) {
                // 实时：插入当前流式气泡内的工具区
                _addToolCallToStreamingBubble(msg.data);
            } else {
                // 回放：缓存，等待 assistant_message 一起渲染
                _pendingToolCalls.push(msg.data);
            }
            break;

        case 'done':
            isStreaming = false;
            _finalizeStreamingBubble();
            updateTokenBar(msg.usage);
            $('btn-send').disabled = false;
            break;

        case 'error':
            isStreaming = false;
            showToast(msg.message || '发生错误', 'error');
            $('btn-send').disabled = false;
            document.querySelectorAll('.message.assistant.streaming').forEach(el => el.remove());
            break;

        case 'cleared':
            $('chat-messages').innerHTML = '';
            msgCount = 0;
            updateBadge();
            _pendingToolCalls = [];
            showToast('对话已清空', 'info');
            break;

        /* == 历史回放 == */
        case 'assistant_message':
            // 把缓存的 tool_calls 一并传入
            addCompletedAssistantMessage(msg.content, _pendingToolCalls);
            _pendingToolCalls = [];
            break;

        /* == 危险命令确认 == */
        case 'confirm_request':
            showConfirmModal(msg.id, msg.command);
            break;
    }
}

/* ─── 自发消息去重 ───────────────────────────────── */
let _lastSentText = null;
function _isSelf(text) {
    if (_lastSentText === text) { _lastSentText = null; return true; }
    return false;
}

/* ─── 用户消息 ───────────────────────────────────── */
function addUserMessage(text) {
    msgCount++;
    updateBadge();
    const div = document.createElement('div');
    div.className = 'message user';
    div.innerHTML = `
        <div class="avatar user-avatar">我</div>
        <div class="bubble user-bubble">${escapeHtml(text)}</div>`;
    $('chat-messages').appendChild(div);
    scrollToBottom();
}

/* ─── 工具调用数据 → 展示信息 ───────────────────── */
function _parseToolCallData(data) {
    const name = data.name;
    const args = data.arguments || {};
    if (name === 'use_skill') {
        return {
            cls:    'skill',
            icon:   '⚡',
            brief:  `使用技能: ${args.skill_name || '?'}`,
            detail: `技能名称: ${args.skill_name || '?'}`,
        };
    } else if (name === 'bash') {
        const cmd = args.command || '';
        return {
            cls:    'bash',
            icon:   '⚙',
            brief:  '使用工具: Bash',
            detail: cmd,
        };
    } else {
        return {
            cls:    '',
            icon:   '🔧',
            brief:  `工具调用: ${name}`,
            detail: JSON.stringify(args, null, 2),
        };
    }
}

/* ─── 构建折叠工具调用 DOM ─────────────────────── */
function _buildToolCallItem({ cls, icon, brief, detail }) {
    const item = document.createElement('div');
    item.className = `tool-item ${cls}`;

    const summary = document.createElement('div');
    summary.className = 'tool-summary';
    summary.innerHTML = `
        <span class="tool-toggle">▶</span>
        <span class="tool-icon-sm">${icon}</span>
        <span class="tool-brief">${escapeHtml(brief)}</span>`;
    summary.addEventListener('click', () => {
        item.classList.toggle('expanded');
        summary.querySelector('.tool-toggle').textContent =
            item.classList.contains('expanded') ? '▼' : '▶';
    });

    const detailEl = document.createElement('div');
    detailEl.className = 'tool-detail';
    detailEl.innerHTML = `<pre>${escapeHtml(detail)}</pre>`;

    item.appendChild(summary);
    item.appendChild(detailEl);
    return item;
}

/* ─── 向流式气泡插入工具调用 ────────────────────── */
function _addToolCallToStreamingBubble(data) {
    const msgs = $('chat-messages').querySelectorAll('.message.assistant.streaming');
    if (!msgs.length) return;
    const bubble = msgs[msgs.length - 1];
    const group = bubble.querySelector('.tool-calls-group');
    if (!group) return;
    group.hidden = false;
    group.appendChild(_buildToolCallItem(_parseToolCallData(data)));
    scrollToBottom();
}

/* ─── 创建流式气泡（含工具区 + 文字区）────────── */
function _createStreamingBubble() {
    const div = document.createElement('div');
    div.className = 'message assistant streaming';
    div.dataset.raw = '';
    div.innerHTML = `
        <div class="avatar ai-avatar">AI</div>
        <div class="msg-right">
            <div class="tool-calls-group" hidden></div>
            <div class="bubble ai-bubble">
                <div class="content"></div>
                <span class="streaming-cursor"></span>
            </div>
        </div>`;
    $('chat-messages').appendChild(div);
    scrollToBottom();
}

function _appendChunk(text) {
    const msgs = $('chat-messages').querySelectorAll('.message.assistant.streaming');
    if (!msgs.length) return;
    const last = msgs[msgs.length - 1];
    last.dataset.raw = (last.dataset.raw || '') + text;
    last.querySelector('.content').textContent = last.dataset.raw;
    scrollToBottom();
}

function _finalizeStreamingBubble() {
    const msgs = $('chat-messages').querySelectorAll('.message.assistant.streaming');
    if (!msgs.length) return;
    const last = msgs[msgs.length - 1];
    last.classList.remove('streaming');
    const cursor = last.querySelector('.streaming-cursor');
    if (cursor) cursor.remove();
    const content = last.querySelector('.content');
    const raw = last.dataset.raw || '';
    if (raw) {
        content.innerHTML = renderMarkdown(raw);
        _addCopyButtons(content);
    }
    msgCount++;
    updateBadge();
    scrollToBottom();
}

/* ─── 回放：完整 AI 消息（含工具调用）────────── */
function addCompletedAssistantMessage(text, toolCalls = []) {
    msgCount++;
    updateBadge();

    const div = document.createElement('div');
    div.className = 'message assistant';
    div.dataset.raw = text;

    // 构建工具调用区（若有）
    let toolGroupHtml = '';
    if (toolCalls.length > 0) {
        toolGroupHtml = `<div class="tool-calls-group"></div>`;
    }

    div.innerHTML = `
        <div class="avatar ai-avatar">AI</div>
        <div class="msg-right">
            ${toolGroupHtml}
            <div class="bubble ai-bubble">
                <div class="content">${renderMarkdown(text)}</div>
            </div>
        </div>`;

    // 插入工具调用项
    const group = div.querySelector('.tool-calls-group');
    if (group && toolCalls.length > 0) {
        toolCalls.forEach(tc => group.appendChild(_buildToolCallItem(_parseToolCallData(tc))));
    }

    _addCopyButtons(div.querySelector('.content'));
    $('chat-messages').appendChild(div);
    scrollToBottom();
}

/* ─── 代码块复制按钮 ─────────────────────────────── */
function _addCopyButtons(container) {
    if (!container) return;
    container.querySelectorAll('pre').forEach(pre => {
        if (pre.querySelector('.copy-btn')) return;
        const btn = document.createElement('button');
        btn.className = 'copy-btn';
        btn.textContent = '复制';
        btn.onclick = () => {
            const code = pre.querySelector('code');
            navigator.clipboard.writeText(code ? code.textContent : pre.textContent).then(() => {
                btn.textContent = '✓ 已复制';
                setTimeout(() => { btn.textContent = '复制'; }, 2000);
            });
        };
        pre.style.position = 'relative';
        pre.appendChild(btn);
    });
}

/* ─── Token 统计 ─────────────────────────────────── */
function updateTokenBar(usage) {
    if (!usage) { $('token-bar').innerHTML = ''; return; }
    const items = [
        ['输入', usage.prompt_tokens],
        ['输出', usage.completion_tokens],
        ['总计', usage.total_tokens],
        ['缓存', usage.cached_tokens],
        ['推理', usage.reasoning_tokens],
    ].filter(([, v]) => v);
    $('token-bar').innerHTML = items.map(([k, v]) =>
        `<span class="token-item"><span class="label">${k}</span><span class="value">${v.toLocaleString()}</span></span>`
    ).join('');
}

/* ─── 确认弹窗 ───────────────────────────────────── */
function showConfirmModal(id, command) {
    $('confirm-command').textContent = command;
    $('confirm-modal').classList.add('active');
    pendingConfirm = { id };
}

/* ─── 其他工具函数 ───────────────────────────────── */
function updateBadge() {
    const badge = $('nav-badge');
    if (badge) badge.textContent = msgCount;
}

function scrollToBottom() {
    const el = $('chat-messages');
    requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
}

/* ─── 发送消息 ───────────────────────────────────── */
function sendMessage() {
    const input = $('chat-input');
    const text = input.value.trim();
    if (!text || isStreaming) return;

    _lastSentText = text;
    addUserMessage(text);
    input.value = '';
    input.style.height = 'auto';
    $('btn-send').disabled = true;

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'chat', content: text }));
    } else {
        showToast('WebSocket 未连接', 'error');
        $('btn-send').disabled = false;
    }
}

/* ─── 初始化 ─────────────────────────────────────── */
function initChat() {
    $('btn-send').addEventListener('click', sendMessage);

    $('chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });

    $('chat-input').addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 200) + 'px';
    });

    $('btn-clear').addEventListener('click', () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'clear' }));
        }
    });

    $('btn-confirm-yes').addEventListener('click', () => {
        $('confirm-modal').classList.remove('active');
        if (pendingConfirm && ws) {
            ws.send(JSON.stringify({ type: 'confirm', id: pendingConfirm.id, approved: true }));
            pendingConfirm = null;
        }
    });

    $('btn-confirm-no').addEventListener('click', () => {
        $('confirm-modal').classList.remove('active');
        if (pendingConfirm && ws) {
            ws.send(JSON.stringify({ type: 'confirm', id: pendingConfirm.id, approved: false }));
            pendingConfirm = null;
        }
    });
}
