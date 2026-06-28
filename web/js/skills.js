/* ===== 技能管理：列表 + 工作空间（新建/编辑统一） ===== */

// ----- 状态 -----
let currentSkillName = null;   // null = 新建模式，非 null = 编辑模式
let currentFilePath  = null;
let openTabs         = [];     // [{path, content, modified}]
let fileTreeData     = [];
let collapsedPaths   = new Set();
let isFullscreen     = false;
let isScrollSyncing  = false;
let skillMetaOriginal = { name: '', description: '' };

const editorTA = () => $('skill-file-editor');
const previewEl = () => $('markdown-preview');

/* ============================
   技能列表
   ============================ */
async function loadSkills() {
    const skills = await apiGet('/skills');
    const container = $('skills-list');
    if (!skills.length) {
        container.innerHTML = '<div class="empty-state">暂无技能</div>';
        return;
    }
    container.innerHTML = skills.map(s => `
        <div class="list-item">
            <div class="info">
                <div class="name">${escapeHtml(s.name)}</div>
                <div class="desc">${escapeHtml(s.description)}</div>
            </div>
            <div class="actions">
                <button onclick="openSkillWorkspace('${escapeHtml(s.name)}')">编辑</button>
                <button class="danger" onclick="deleteSkill('${escapeHtml(s.name)}')">删除</button>
            </div>
        </div>
    `).join('');
}

window.deleteSkill = async function(name) {
    if (!confirm(`确定删除技能 "${name}" 吗？`)) return;
    const res = await apiDelete(`/skills/${encodeURIComponent(name)}`);
    if (res.error) { showToast(res.error, 'error'); }
    else {
        showToast('已删除', 'success');
        if (currentSkillName === name) closeSkillWorkspace();
        loadSkills();
    }
};

/* ============================
   工作空间开关
   ============================ */

/** 打开工作空间（编辑已有技能） */
window.openSkillWorkspace = async function(name) {
    currentSkillName = name;
    resetWorkspace();
    setWorkspaceTitle('编辑技能: ' + name);
    showWorkspace();

    const skills = await apiGet('/skills');
    const skill = skills.find(s => s.name === name);
    setSkillMeta(name, skill ? skill.description : '');
    setFileTreeEnabled(true);
    await loadFileTree(name);
    renderTabs();
    renderEditor();
};

/** 打开工作空间（新建技能） */
function openNewSkillWorkspace() {
    currentSkillName = null;
    resetWorkspace();
    setWorkspaceTitle('新建技能');
    showWorkspace();
    setSkillMeta('', '');
    setFileTreeEnabled(false); // 先禁用文件操作，等技能创建后再启用
    renderFileTree();
    renderTabs();
    renderEditor();
}

function resetWorkspace() {
    openTabs = [];
    currentFilePath = null;
    fileTreeData = [];
    collapsedPaths.clear();
}

function showWorkspace() {
    $('skill-workspace').style.display = 'block';
    $('skill-workspace').scrollIntoView({ behavior: 'smooth' });
}

function closeSkillWorkspace() {
    $('skill-workspace').style.display = 'none';
    exitFullscreen();
    currentSkillName = null;
    currentFilePath = null;
    openTabs = [];
}

function setWorkspaceTitle(title) {
    $('skill-workspace-title').textContent = title;
}

/** 控制文件树按钮是否可用（新建模式下禁用，待技能保存后启用） */
function setFileTreeEnabled(enabled) {
    const toolbar = $('file-tree-toolbar');
    const disabledMsg = $('file-tree-disabled-msg');
    if (enabled) {
        toolbar.style.display = 'flex';
        if (disabledMsg) disabledMsg.style.display = 'none';
    } else {
        toolbar.style.display = 'none';
        if (disabledMsg) disabledMsg.style.display = 'block';
    }
}

/* ============================
   技能元信息（名称 + 描述）
   ============================ */
function setSkillMeta(name, description) {
    $('skill-meta-name').value = name || '';
    $('skill-meta-desc').value = description || '';
    skillMetaOriginal = { name: name || '', description: description || '' };
}

async function saveSkillMeta() {
    const newName = $('skill-meta-name').value.trim();
    const newDesc = $('skill-meta-desc').value.trim();
    if (!newName) { showToast('名称不能为空', 'error'); return; }

    /* === 新建技能 === */
    if (!currentSkillName) {
        const res = await apiPost('/skills', { name: newName, description: newDesc, body: '' });
        if (res.error) { showToast(res.error, 'error'); return; }
        currentSkillName = newName;
        skillMetaOriginal = { name: newName, description: newDesc };
        setWorkspaceTitle('编辑技能: ' + newName);
        setFileTreeEnabled(true);
        await loadFileTree(newName);
        renderFileTree();
        showToast('技能已创建', 'success');
        loadSkills();
        return;
    }

    /* === 重命名 === */
    if (newName !== skillMetaOriginal.name) {
        // 新建同名技能
        const res = await apiPost('/skills', { name: newName, description: newDesc, body: '' });
        if (res.error) { showToast(res.error, 'error'); return; }
        // 复制所有文件
        await copySkillFiles(currentSkillName, newName, fileTreeData);
        // 删除旧技能
        await apiDelete(`/skills/${encodeURIComponent(currentSkillName)}`);
        currentSkillName = newName;
        skillMetaOriginal = { name: newName, description: newDesc };
        setWorkspaceTitle('编辑技能: ' + newName);
        loadSkills();
        await loadFileTree(newName);
        showToast('技能已重命名并保存', 'success');
        return;
    }

    /* === 仅更新描述 === */
    const res = await apiPost('/skills', { name: currentSkillName, description: newDesc, body: '' });
    if (res.error) { showToast(res.error, 'error'); }
    else {
        skillMetaOriginal.description = newDesc;
        showToast('描述已保存', 'success');
        loadSkills();
    }
}

async function copySkillFiles(srcName, dstName, items, prefix = '') {
    for (const item of items) {
        const itemPath = prefix ? prefix + '/' + item.name : item.name;
        if (item.type === 'folder') {
            await apiPost(`/skills/${encodeURIComponent(dstName)}/files`, { path: itemPath, type: 'folder' });
            if (item.children) await copySkillFiles(srcName, dstName, item.children, itemPath);
        } else {
            const fileRes = await apiGet(`/skills/${encodeURIComponent(srcName)}/files/${encodeURIComponent(item.path)}`);
            await apiPost(`/skills/${encodeURIComponent(dstName)}/files/${encodeURIComponent(itemPath)}`, { content: fileRes.content || '' });
        }
    }
}

/* ============================
   文件树
   ============================ */
async function loadFileTree(name) {
    const res = await apiGet(`/skills/${encodeURIComponent(name)}/files`);
    if (res.error) { showToast(res.error, 'error'); return; }
    fileTreeData = res.tree || [];
    renderFileTree();
}

function renderFileTree() {
    const container = $('skill-file-tree');
    container.innerHTML = '';
    fileTreeData.forEach(item => container.appendChild(buildTreeNode(item, 0)));
}

function buildTreeNode(item, depth) {
    const div = document.createElement('div');
    const isFolder   = item.type === 'folder';
    const isCollapsed = collapsedPaths.has(item.path);
    const hasChildren = isFolder && item.children && item.children.length > 0;

    div.innerHTML = `
        <div class="tree-item${currentFilePath === item.path ? ' active' : ''}"
             data-path="${escapeHtml(item.path)}" data-type="${item.type}">
            ${hasChildren
                ? `<span class="tree-toggle ${isCollapsed ? 'collapsed' : ''}">▼</span>`
                : '<span style="width:14px;flex-shrink:0;"></span>'}
            <span class="tree-icon">${isFolder ? '📁' : '📄'}</span>
            <span class="tree-name">${escapeHtml(item.name)}</span>
            <div class="tree-actions">
                ${isFolder
                    ? `<button onclick="event.stopPropagation();newTreeItem('${escapeHtml(item.path)}', 'file')" title="新建文件">+f</button>
                       <button onclick="event.stopPropagation();newTreeItem('${escapeHtml(item.path)}', 'folder')" title="新建文件夹">+d</button>`
                    : ''}
                <button onclick="event.stopPropagation();deleteTreeItem('${escapeHtml(item.path)}')" title="删除">×</button>
            </div>
        </div>
    `;

    const itemEl = div.querySelector('.tree-item');
    itemEl.addEventListener('click', () => {
        if (isFolder) {
            isCollapsed ? collapsedPaths.delete(item.path) : collapsedPaths.add(item.path);
            renderFileTree();
        } else {
            openFile(item.path);
        }
    });

    if (isFolder && item.children && !isCollapsed) {
        const childrenDiv = document.createElement('div');
        childrenDiv.className = 'tree-children';
        item.children.forEach(child => childrenDiv.appendChild(buildTreeNode(child, depth + 1)));
        div.appendChild(childrenDiv);
    }

    return div;
}

/* ============================
   文件树操作
   ============================ */
window.newTreeItem = async function(parentPath, type) {
    if (!currentSkillName) return;
    const name = prompt(type === 'folder' ? '文件夹名称:' : '文件名称:');
    if (!name) return;
    const newPath = parentPath ? parentPath + '/' + name : name;
    const res = await apiPost(`/skills/${encodeURIComponent(currentSkillName)}/files`, { path: newPath, type });
    if (res.error) { showToast(res.error, 'error'); }
    else { showToast('已创建', 'success'); loadFileTree(currentSkillName); }
};

window.deleteTreeItem = async function(path) {
    if (!currentSkillName) return;
    if (!confirm(`确定删除 "${path}" 吗？`)) return;
    const res = await apiDelete(`/skills/${encodeURIComponent(currentSkillName)}/files/${encodeURIComponent(path)}`);
    if (res.error) { showToast(res.error, 'error'); }
    else {
        showToast('已删除', 'success');
        const tabIdx = openTabs.findIndex(t => t.path === path);
        if (tabIdx >= 0) {
            openTabs.splice(tabIdx, 1);
            if (currentFilePath === path) {
                currentFilePath = openTabs.length > 0 ? openTabs[openTabs.length - 1].path : null;
            }
            renderTabs();
            renderEditor();
        }
        loadFileTree(currentSkillName);
    }
};

/* ============================
   文件打开 / Tab
   ============================ */
async function openFile(path) {
    if (!currentSkillName) return;
    const existing = openTabs.find(t => t.path === path);
    if (existing) {
        currentFilePath = path;
        renderTabs();
        renderEditor();
        return;
    }
    const res = await apiGet(`/skills/${encodeURIComponent(currentSkillName)}/files/${encodeURIComponent(path)}`);
    if (res.error) { showToast(res.error, 'error'); return; }
    openTabs.push({ path, content: res.content || '', modified: false });
    currentFilePath = path;
    renderTabs();
    renderEditor();
}

function renderTabs() {
    const container = $('editor-tabs');
    if (openTabs.length === 0) { container.innerHTML = ''; return; }
    container.innerHTML = openTabs.map(tab => {
        const name = tab.path.split('/').pop();
        const isActive = tab.path === currentFilePath;
        return `
            <div class="editor-tab ${isActive ? 'active' : ''}" data-path="${escapeHtml(tab.path)}">
                <span>${escapeHtml(name)}${tab.modified ? ' *' : ''}</span>
                <span class="tab-close" data-path="${escapeHtml(tab.path)}">×</span>
            </div>
        `;
    }).join('');

    container.querySelectorAll('.editor-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            if (e.target.classList.contains('tab-close')) {
                closeTab(e.target.dataset.path);
            } else {
                currentFilePath = tab.dataset.path;
                renderTabs();
                renderEditor();
            }
        });
    });
}

function closeTab(path) {
    const idx = openTabs.findIndex(t => t.path === path);
    if (idx < 0) return;
    if (openTabs[idx].modified && !confirm('文件已修改，确定关闭而不保存吗？')) return;
    openTabs.splice(idx, 1);
    if (currentFilePath === path) {
        currentFilePath = openTabs.length > 0 ? openTabs[openTabs.length - 1].path : null;
    }
    renderTabs();
    renderEditor();
}

/* ============================
   编辑器渲染
   ============================ */
function isMarkdownFile(path) {
    return path && (path.endsWith('.md') || path.endsWith('.markdown'));
}

function renderEditor() {
    const editor  = editorTA();
    const preview = previewEl();
    const status  = $('editor-status');

    if (!currentFilePath || openTabs.length === 0) {
        editor.value = '';
        editor.disabled = true;
        editor.placeholder = '选择左侧文件开始编辑...';
        preview.innerHTML = '<div class="editor-empty"><span>📄</span><span>选择文件查看预览</span></div>';
        status.textContent = '就绪';
        return;
    }

    const tab = openTabs.find(t => t.path === currentFilePath);
    if (!tab) return;

    editor.disabled = false;
    editor.value = tab.content;
    editor.placeholder = '';
    status.textContent = tab.modified ? '已修改' : '已保存';

    if (isMarkdownFile(tab.path)) {
        preview.innerHTML = renderMarkdown(tab.content);
    } else {
        preview.innerHTML = '<div class="editor-empty"><span>👁</span><span>非 Markdown 文件，无预览</span></div>';
    }
}

/* ============================
   同步滚动（始终生效，不限于全屏）
   ============================ */
function syncScroll(source, target) {
    if (isScrollSyncing) return;
    isScrollSyncing = true;
    const ratio = source.scrollTop / (source.scrollHeight - source.clientHeight || 1);
    target.scrollTop = ratio * (target.scrollHeight - target.clientHeight || 1);
    requestAnimationFrame(() => { isScrollSyncing = false; });
}

/* ============================
   全屏切换
   ============================ */
function enterFullscreen() {
    isFullscreen = true;
    $('skill-workspace-body').classList.add('fullscreen');
    $('btn-toggle-fullscreen').title = '退出全屏 (Esc)';
    $('btn-toggle-fullscreen').innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/>
        </svg>`;
}

function exitFullscreen() {
    isFullscreen = false;
    $('skill-workspace-body').classList.remove('fullscreen');
    $('btn-toggle-fullscreen').title = '全屏';
    $('btn-toggle-fullscreen').innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
        </svg>`;
}

/* ============================
   初始化
   ============================ */
function initSkills() {
    /* ----- 工作空间开关 ----- */
    $('btn-close-skill-workspace').addEventListener('click', () => closeSkillWorkspace());

    /* ----- 全屏 ----- */
    $('btn-toggle-fullscreen').addEventListener('click', () => {
        isFullscreen ? exitFullscreen() : enterFullscreen();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isFullscreen) exitFullscreen();
    });

    /* ----- 元信息保存 ----- */
    $('btn-save-meta').addEventListener('click', saveSkillMeta);

    /* ----- 编辑器输入 → 实时预览 ----- */
    $('skill-file-editor').addEventListener('input', () => {
        const tab = openTabs.find(t => t.path === currentFilePath);
        if (!tab) return;
        tab.content = editorTA().value;
        tab.modified = true;
        $('editor-status').textContent = '已修改';
        renderTabs();
        if (isMarkdownFile(tab.path)) {
            previewEl().innerHTML = renderMarkdown(tab.content);
        }
    });

    /* ----- 同步滚动（始终启用） ----- */
    $('skill-file-editor').addEventListener('scroll', () => {
        if (isMarkdownFile(currentFilePath)) syncScroll(editorTA(), previewEl());
    });

    $('markdown-preview').addEventListener('scroll', () => {
        if (isMarkdownFile(currentFilePath)) syncScroll(previewEl(), editorTA());
    });

    /* ----- 保存文件 ----- */
    $('btn-save-file').addEventListener('click', async () => {
        if (!currentSkillName || !currentFilePath) return;
        const tab = openTabs.find(t => t.path === currentFilePath);
        if (!tab) return;
        const res = await apiPost(
            `/skills/${encodeURIComponent(currentSkillName)}/files/${encodeURIComponent(currentFilePath)}`,
            { content: tab.content }
        );
        if (res.error) { showToast(res.error, 'error'); }
        else {
            tab.modified = false;
            $('editor-status').textContent = '已保存';
            renderTabs();
            showToast('已保存', 'success');
        }
    });

    /* ----- 新建文件 / 文件夹 ----- */
    $('btn-new-file').addEventListener('click', () => {
        if (!currentSkillName) { showToast('请先保存技能基础信息', 'info'); return; }
        newTreeItem('', 'file');
    });

    $('btn-new-folder').addEventListener('click', () => {
        if (!currentSkillName) { showToast('请先保存技能基础信息', 'info'); return; }
        newTreeItem('', 'folder');
    });

    /* ----- 上传文件 ----- */
    $('btn-upload-file').addEventListener('click', () => {
        if (!currentSkillName) { showToast('请先保存技能基础信息', 'info'); return; }
        $('file-upload-input').click();
    });

    $('file-upload-input').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file || !currentSkillName) return;
        const reader = new FileReader();
        reader.onload = async (ev) => {
            const base64 = ev.target.result.split(',')[1];
            const res = await apiPost(`/skills/${encodeURIComponent(currentSkillName)}/upload`, {
                path: file.name,
                data: base64,
            });
            if (res.error) { showToast(res.error, 'error'); }
            else { showToast('上传成功', 'success'); loadFileTree(currentSkillName); }
        };
        reader.readAsDataURL(file);
        e.target.value = '';
    });

    /* ----- 新建技能按钮（使用工作空间代替 prompt） ----- */
    $('btn-add-skill').addEventListener('click', openNewSkillWorkspace);

    /* ----- Ctrl+S 保存 ----- */
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 's' && currentFilePath) {
            e.preventDefault();
            $('btn-save-file').click();
        }
    });
}
