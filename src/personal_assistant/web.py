"""Web 服务入口：提供 REST API + WebSocket 实时对话，复用现有 Agent 核心逻辑。

架构：
- FastAPI 提供 HTTP REST API（配置、工具、技能、黑名单的 CRUD）
- WebSocket /ws/chat 提供流式对话（复用 Agent.run + on_chunk 回调）
- 静态文件服务提供前端 SPA
"""

from __future__ import annotations

import asyncio
import io
import json
import re
import socket
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from personal_assistant.config import ConfigError, ModelConfig, load_config, _DEFAULT_CONFIG_PATH, _EXAMPLE_CONFIG_PATH
from personal_assistant.core.agent import Agent
from personal_assistant.core.protocol import Message
from personal_assistant.core.skill import SkillManager
from personal_assistant.llm.client import LLMClient
from personal_assistant.skills import default_skill_manager
from personal_assistant.tools import default_tools

# --------------------------------------------------------------------------- #
# 路径常量
# --------------------------------------------------------------------------- #
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = _PROJECT_ROOT / "config"
_BLACKLIST_PATH = _CONFIG_DIR / "bash_blacklist.txt"
_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

# --------------------------------------------------------------------------- #
# 全局状态（单进程内共享）
# --------------------------------------------------------------------------- #

class _AppState:
    """运行时共享状态。"""

    agent: Agent | None = None
    config: ModelConfig | None = None
    llm: LLMClient | None = None
    skill_manager: SkillManager | None = None
    blacklist_patterns: list[re.Pattern[str]] = []


app_state = _AppState()

# --------------------------------------------------------------------------- #
# 初始化 / 重新加载
# --------------------------------------------------------------------------- #


def _load_blacklist() -> list[re.Pattern[str]]:
    """加载 bash 命令黑名单文件，编译为正则列表。"""
    patterns: list[re.Pattern[str]] = []
    if not _BLACKLIST_PATH.exists():
        return patterns
    for line in _BLACKLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append(re.compile(line, re.IGNORECASE))
        except re.error:
            pass
    return patterns


def _is_dangerous(command: str) -> bool:
    return any(p.search(command) for p in app_state.blacklist_patterns)


def _build_agent() -> None:
    """根据当前配置重建 Agent 实例。"""
    cfg = app_state.config
    if cfg is None:
        raise RuntimeError("Config not loaded")

    app_state.llm = LLMClient(cfg)
    app_state.skill_manager = default_skill_manager()

    app_state.agent = Agent(
        app_state.llm,
        tools=default_tools(),
        system_prompt=cfg.system_prompt,
        confirm=_web_confirm,
        on_event=_web_on_event,
        skills=app_state.skill_manager,
    )


def _reload_config() -> None:
    """重新加载配置并重建 Agent。"""
    try:
        app_state.config = load_config()
    except ConfigError:
        # 如果 model.json 不存在或无效，使用 example 作为兜底
        if _EXAMPLE_CONFIG_PATH.exists():
            try:
                app_state.config = load_config(_EXAMPLE_CONFIG_PATH)
            except ConfigError:
                app_state.config = ModelConfig()
        else:
            app_state.config = ModelConfig()
    app_state.blacklist_patterns = _load_blacklist()
    try:
        _build_agent()
    except Exception:
        # Agent 构建失败（如 API key 无效）不影响 Web 服务启动
        pass


# --------------------------------------------------------------------------- #
# WebSocket 对话辅助  —  广播架构（PC + 手机共享会话）
# --------------------------------------------------------------------------- #

# 所有活跃的 WebSocket 连接（PC + 手机）
_active_connections: set[WebSocket] = set()

# 共享对话历史（所有客户端共用）
_shared_history: list[Message] = []

# 事件回放日志（新客户端连接时重播历史）
_event_log: list[dict] = []

# 序列化 Agent 调用（同时只允许一个对话进行）
_chat_lock = asyncio.Lock()

# 待确认队列：工具调用 → 等待前端响应
_pending_confirms: dict[str, asyncio.Future[bool]] = {}


def _get_local_ip() -> str:
    """获取本机局域网 IP 地址（用于生成手机访问链接）。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def _broadcast(msg: dict, log: bool = False) -> None:
    """向所有已连接的 WebSocket 客户端广播消息。"""
    global _active_connections
    if log:
        _event_log.append(msg)
    dead: set[WebSocket] = set()
    for ws in list(_active_connections):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.add(ws)
    if dead:
        _active_connections = _active_connections - dead


async def _web_confirm(name: str, arguments: dict, preview: str) -> bool:
    """Web 端工具确认：危险命令广播给所有客户端等待确认。"""
    if name == "use_skill":
        return True
    if name == "bash":
        command = str(arguments.get("command", ""))
        if not _is_dangerous(command):
            return True
        # 危险命令：广播确认请求，等待任意客户端响应
        confirm_id = f"confirm_{name}_{id(asyncio.current_task())}"
        loop = asyncio.get_event_loop()
        future: asyncio.Future[bool] = loop.create_future()
        _pending_confirms[confirm_id] = future
        asyncio.run_coroutine_threadsafe(
            _broadcast({"type": "confirm_request", "id": confirm_id, "command": command}),
            loop,
        )
        try:
            return await asyncio.wait_for(future, timeout=60.0)
        except asyncio.TimeoutError:
            return False
        finally:
            _pending_confirms.pop(confirm_id, None)
    return True


def _web_on_event(event: str, data: dict) -> None:
    """由 agent.on_event 覆盖后不再使用（回调在 chat_handler 中动态注入）。"""
    pass


# --------------------------------------------------------------------------- #
# FastAPI 应用
# --------------------------------------------------------------------------- #


@asynccontextmanager
async def lifespan(app: FastAPI):
    _reload_config()
    # 初始化共享对话历史
    cfg = app_state.config
    sys_prompt = cfg.system_prompt if cfg else "你是一个乐于助人的个人助理。"
    _shared_history.clear()
    _shared_history.append(Message.system(sys_prompt))
    yield
    # 清理
    _active_connections.clear()
    _shared_history.clear()
    _event_log.clear()
    _pending_confirms.clear()


app = FastAPI(title="Personal Assistant Web", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件（前端 SPA）
_static_dir = _PROJECT_ROOT / "web"
# 挂载 web/ 目录下的 CSS/JS 等静态资源
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# --------------------------------------------------------------------------- #
# REST API — 配置管理
# --------------------------------------------------------------------------- #


@app.get("/api/config")
def get_config() -> dict:
    cfg = app_state.config
    if cfg is None:
        return {"error": "Config not loaded"}
    return {
        "base_url": cfg.base_url,
        "model": cfg.model,
        "system_prompt": cfg.system_prompt,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
        "stream": cfg.stream,
        "extra": cfg.extra,
    }


@app.post("/api/config")
def update_config(payload: dict) -> dict:
    """更新 model.json 配置并重建 Agent。"""
    # 读取现有配置，合并更新
    try:
        current = load_config()
    except ConfigError:
        current = ModelConfig()

    allowed = {"base_url", "api_key", "model", "system_prompt", "temperature", "max_tokens", "stream"}
    for key, value in payload.items():
        if key in allowed:
            setattr(current, key, value)

    # 写回文件
    _DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "base_url": current.base_url,
        "api_key": current.api_key,
        "model": current.model,
        "system_prompt": current.system_prompt,
        "temperature": current.temperature,
        "max_tokens": current.max_tokens,
        "stream": current.stream,
    }
    if current.extra:
        data.update(current.extra)
    _DEFAULT_CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    _reload_config()
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# REST API — 工具管理
# --------------------------------------------------------------------------- #


@app.get("/api/tools")
def list_tools() -> list[dict]:
    agent = app_state.agent
    if agent is None:
        return []
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        }
        for t in agent.tools.values()
        if t.name != "use_skill"  # use_skill 是系统工具，不展示
    ]


# --------------------------------------------------------------------------- #
# REST API — 技能管理
# --------------------------------------------------------------------------- #


@app.get("/api/skills")
def list_skills() -> list[dict]:
    sm = app_state.skill_manager
    if sm is None:
        return []
    return [
        {
            "name": s.name,
            "description": s.description,
            "folder": str(s.folder_path),
        }
        for s in sm.list()
    ]


@app.get("/api/skills/{name}")
def get_skill(name: str) -> dict:
    sm = app_state.skill_manager
    if sm is None:
        return {"error": "Skill manager not loaded"}
    skill = sm.get(name)
    if skill is None:
        return {"error": "Skill not found"}
    return {
        "name": skill.name,
        "description": skill.description,
        "body": skill.body,
        "folder": str(skill.folder_path),
        "content": skill.load_content(),
    }


@app.post("/api/skills")
def create_skill(payload: dict) -> dict:
    """创建新技能：在 skills/ 下创建文件夹 + SKILL.md。"""
    name = payload.get("name", "").strip()
    description = payload.get("description", "").strip()
    body = payload.get("body", "").strip()
    if not name:
        return {"error": "技能名称不能为空"}

    folder = _SKILLS_DIR / name
    if folder.exists():
        return {"error": f"技能 '{name}' 已存在"}

    folder.mkdir(parents=True, exist_ok=True)
    skill_md = f"# {name}\n\n> {description}\n\n{body}\n"
    (folder / "SKILL.md").write_text(skill_md, encoding="utf-8")

    # 重新加载
    _reload_config()
    return {"status": "ok", "name": name}


@app.put("/api/skills/{name}")
def update_skill(name: str, payload: dict) -> dict:
    """更新技能内容。"""
    sm = app_state.skill_manager
    if sm is None:
        return {"error": "Skill manager not loaded"}
    skill = sm.get(name)
    if skill is None:
        return {"error": "Skill not found"}

    new_name = payload.get("name", name).strip()
    description = payload.get("description", skill.description).strip()
    body = payload.get("body", skill.body).strip()

    folder = skill.folder_path
    skill_md = f"# {new_name}\n\n> {description}\n\n{body}\n"
    (folder / "SKILL.md").write_text(skill_md, encoding="utf-8")

    # 如果改名了，重命名文件夹
    if new_name != name:
        new_folder = _SKILLS_DIR / new_name
        folder.rename(new_folder)

    _reload_config()
    return {"status": "ok"}


@app.delete("/api/skills/{name}")
def delete_skill(name: str) -> dict:
    """删除技能文件夹。"""
    sm = app_state.skill_manager
    if sm is None:
        return {"error": "Skill manager not loaded"}
    skill = sm.get(name)
    if skill is None:
        return {"error": "Skill not found"}

    import shutil
    shutil.rmtree(skill.folder_path)
    _reload_config()
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# REST API — 技能文件树管理
# --------------------------------------------------------------------------- #


def _skill_folder(name: str) -> Path | None:
    """获取技能文件夹路径，返回 None 表示不存在。"""
    sm = app_state.skill_manager
    if sm is None:
        return None
    skill = sm.get(name)
    if skill is None:
        return None
    return skill.folder_path


def _build_tree(folder: Path, rel_root: Path) -> list[dict]:
    """递归构建文件树列表。"""
    items: list[dict] = []
    for p in sorted(folder.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        rel = str(p.relative_to(rel_root)).replace("\\", "/")
        item: dict = {
            "name": p.name,
            "path": rel,
            "type": "folder" if p.is_dir() else "file",
        }
        if p.is_dir():
            item["children"] = _build_tree(p, rel_root)
        items.append(item)
    return items


@app.get("/api/skills/{name}/files")
def list_skill_files(name: str) -> dict:
    """获取技能文件夹的文件树。"""
    folder = _skill_folder(name)
    if folder is None:
        return {"error": "Skill not found"}
    if not folder.exists():
        return {"tree": []}
    return {"tree": _build_tree(folder, folder)}


@app.get("/api/skills/{name}/files/{file_path:path}")
def read_skill_file(name: str, file_path: str) -> dict:
    """读取技能文件夹中的文件内容。"""
    folder = _skill_folder(name)
    if folder is None:
        return {"error": "Skill not found"}
    target = folder / file_path
    # 安全检查：确保在技能文件夹内
    try:
        target.resolve().relative_to(folder.resolve())
    except ValueError:
        return {"error": "Invalid path"}
    if not target.exists():
        return {"error": "File not found"}
    if target.is_dir():
        return {"error": "Path is a directory"}
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"error": "File is not text-readable"}
    return {"content": content, "path": file_path}


@app.post("/api/skills/{name}/files/{file_path:path}")
def save_skill_file(name: str, file_path: str, payload: dict) -> dict:
    """保存文件内容（覆盖写入）。"""
    folder = _skill_folder(name)
    if folder is None:
        return {"error": "Skill not found"}
    target = folder / file_path
    try:
        target.resolve().relative_to(folder.resolve())
    except ValueError:
        return {"error": "Invalid path"}
    target.parent.mkdir(parents=True, exist_ok=True)
    content = payload.get("content", "")
    target.write_text(content, encoding="utf-8")
    return {"status": "ok"}


@app.post("/api/skills/{name}/files")
def create_skill_file(name: str, payload: dict) -> dict:
    """在技能文件夹中创建新文件或文件夹。"""
    folder = _skill_folder(name)
    if folder is None:
        return {"error": "Skill not found"}
    file_path = payload.get("path", "").strip()
    file_type = payload.get("type", "file")  # "file" or "folder"
    if not file_path:
        return {"error": "Path is required"}
    target = folder / file_path
    try:
        target.resolve().relative_to(folder.resolve())
    except ValueError:
        return {"error": "Invalid path"}
    if target.exists():
        return {"error": "Already exists"}
    if file_type == "folder":
        target.mkdir(parents=True, exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    return {"status": "ok"}


@app.delete("/api/skills/{name}/files/{file_path:path}")
def delete_skill_file(name: str, file_path: str) -> dict:
    """删除技能文件夹中的文件或文件夹。"""
    folder = _skill_folder(name)
    if folder is None:
        return {"error": "Skill not found"}
    target = folder / file_path
    try:
        target.resolve().relative_to(folder.resolve())
    except ValueError:
        return {"error": "Invalid path"}
    if not target.exists():
        return {"error": "Not found"}
    import shutil
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"status": "ok"}


@app.post("/api/skills/{name}/upload")
def upload_skill_file(name: str, payload: dict) -> dict:
    """上传文件到技能文件夹（base64 编码）。"""
    folder = _skill_folder(name)
    if folder is None:
        return {"error": "Skill not found"}
    import base64
    file_path = payload.get("path", "").strip()
    file_data = payload.get("data", "")
    if not file_path or not file_data:
        return {"error": "Path and data are required"}
    target = folder / file_path
    try:
        target.resolve().relative_to(folder.resolve())
    except ValueError:
        return {"error": "Invalid path"}
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        decoded = base64.b64decode(file_data)
    except Exception:
        return {"error": "Invalid base64 data"}
    target.write_bytes(decoded)
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# REST API — 黑名单管理
# --------------------------------------------------------------------------- #


@app.get("/api/blacklist")
def get_blacklist() -> list[str]:
    if not _BLACKLIST_PATH.exists():
        return []
    lines = []
    for line in _BLACKLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


@app.post("/api/blacklist")
def add_blacklist_rule(payload: dict) -> dict:
    rule = payload.get("rule", "").strip()
    if not rule:
        return {"error": "规则不能为空"}
    try:
        re.compile(rule, re.IGNORECASE)
    except re.error as exc:
        return {"error": f"无效的正则表达式: {exc}"}

    existing = []
    if _BLACKLIST_PATH.exists():
        existing = _BLACKLIST_PATH.read_text(encoding="utf-8").splitlines()

    if rule in [l.strip() for l in existing if not l.strip().startswith("#")]:
        return {"error": "规则已存在"}

    existing.append(rule)
    _BLACKLIST_PATH.write_text("\n".join(existing) + "\n", encoding="utf-8")
    app_state.blacklist_patterns = _load_blacklist()
    return {"status": "ok"}


@app.delete("/api/blacklist")
def remove_blacklist_rule(payload: dict) -> dict:
    rule = payload.get("rule", "").strip()
    if not rule or not _BLACKLIST_PATH.exists():
        return {"error": "规则不存在"}

    lines = _BLACKLIST_PATH.read_text(encoding="utf-8").splitlines()
    new_lines = [l for l in lines if l.strip() != rule]
    _BLACKLIST_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    app_state.blacklist_patterns = _load_blacklist()
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# WebSocket — 实时对话（广播架构，PC + 手机共享同一会话）
# --------------------------------------------------------------------------- #


@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    _active_connections.add(websocket)

    # 向新客户端回放历史消息
    for evt in list(_event_log):
        try:
            await websocket.send_json(evt)
        except Exception:
            break

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            if msg_type == "chat":
                user_text = msg.get("content", "").strip()
                if not user_text:
                    continue

                # 序列化处理（一次只处理一条消息）
                async with _chat_lock:
                    await _handle_chat(user_text)

            elif msg_type == "confirm":
                confirm_id = msg.get("id", "")
                approved = msg.get("approved", False)
                future = _pending_confirms.get(confirm_id)
                if future and not future.done():
                    future.set_result(approved)

            elif msg_type == "clear":
                cfg = app_state.config
                sys_prompt = cfg.system_prompt if cfg else "你是一个乐于助人的个人助理。"
                _shared_history.clear()
                _shared_history.append(Message.system(sys_prompt))
                _event_log.clear()
                await _broadcast({"type": "cleared"})

    except WebSocketDisconnect:
        pass
    finally:
        _active_connections.discard(websocket)


async def _handle_chat(user_text: str) -> None:
    """处理用户消息，向所有客户端广播 Agent 响应。"""
    # 记录用户消息
    _shared_history.append(Message.user(user_text))
    user_evt = {"type": "user_message", "content": user_text}
    _event_log.append(user_evt)
    # 广播用户消息（让其他设备也能看到是谁发的）
    await _broadcast({"type": "user_message", "content": user_text})
    await _broadcast({"type": "start"})

    loop = asyncio.get_event_loop()
    chunks: list[str] = []

    def on_chunk(chunk: str) -> None:
        chunks.append(chunk)
        asyncio.run_coroutine_threadsafe(
            _broadcast({"type": "chunk", "content": chunk}), loop
        )

    def on_event(event: str, data: dict) -> None:
        if event == "tool_call":
            asyncio.run_coroutine_threadsafe(
                _broadcast({"type": "tool_call", "data": data}, log=True), loop
            )

    agent = app_state.agent
    if agent is None:
        await _broadcast({"type": "error", "message": "Agent 未就绪，请检查配置"})
        return

    original_on_event = agent.on_event
    agent.on_event = on_event
    try:
        # 传递共享历史（in-place 修改，agent 会追加 assistant/tool 消息）
        await asyncio.to_thread(agent.run, _shared_history, on_chunk=on_chunk)
    except Exception as exc:
        await _broadcast({"type": "error", "message": str(exc)})
    finally:
        agent.on_event = original_on_event

    # 记录完整 AI 回复（用于历史回放）
    full_text = "".join(chunks)
    if full_text:
        _event_log.append({"type": "assistant_message", "content": full_text})

    usage = agent.last_usage if agent else None
    await _broadcast({
        "type": "done",
        "usage": {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
            "cached_tokens": usage.cached_tokens if usage else 0,
            "reasoning_tokens": usage.reasoning_tokens if usage else 0,
        } if usage else None,
    })


# --------------------------------------------------------------------------- #
# 附加 API：服务器信息 + 二维码 + 手机访问页
# --------------------------------------------------------------------------- #


@app.get("/api/server-info")
def server_info(request: Request) -> dict:
    """返回本机局域网 IP、端口及手机访问 URL。"""
    ip = _get_local_ip()
    port = request.url.port or 8000
    mobile_url = f"http://{ip}:{port}/mobile"
    return {"local_ip": ip, "port": port, "mobile_url": mobile_url}


@app.get("/api/qrcode.svg")
def qrcode_endpoint(request: Request) -> Response:
    """生成二维码 SVG，内容为手机访问 URL。"""
    ip = _get_local_ip()
    port = request.url.port or 8000
    mobile_url = f"http://{ip}:{port}/mobile"

    try:
        import qrcode  # type: ignore[import]
        import qrcode.image.svg  # type: ignore[import]

        factory = qrcode.image.svg.SvgImage
        img = qrcode.make(mobile_url, image_factory=factory, box_size=6, border=3)
        buf = io.BytesIO()
        img.save(buf)
        return Response(content=buf.getvalue(), media_type="image/svg+xml")
    except ImportError:
        # 返回简单的文字 SVG 作为兜底
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60">'
            f'<rect width="200" height="60" fill="#fff" rx="8"/>'
            f'<text x="100" y="35" text-anchor="middle" font-size="12" fill="#333">{mobile_url}</text>'
            f"</svg>"
        )
        return Response(content=svg, media_type="image/svg+xml")


@app.get("/mobile", response_class=HTMLResponse)
def mobile_page() -> str:
    """手机端访问页面。"""
    mobile_html = _static_dir / "mobile.html"
    if mobile_html.exists():
        return mobile_html.read_text(encoding="utf-8")
    return "<h1>mobile.html not found</h1>"


# --------------------------------------------------------------------------- #
# 前端 SPA 入口
# --------------------------------------------------------------------------- #


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """返回前端 SPA 入口 HTML。"""
    # 如果 dist 目录存在，直接返回 index.html
    index_html = _static_dir / "index.html"
    if index_html.exists():
        return index_html.read_text(encoding="utf-8")

    # 否则返回内嵌的简易 HTML（开发阶段）
    return """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Personal Assistant</title></head>
<body>
<h1>Personal Assistant Web</h1>
<p>前端构建中，请稍后刷新。</p>
</body>
</html>"""


# --------------------------------------------------------------------------- #
# 启动入口
# --------------------------------------------------------------------------- #

def main() -> None:
    """Web 服务 CLI 入口。监听所有网络接口，局域网内手机可直接访问。"""
    import uvicorn

    host = "0.0.0.0"
    port = 8000
    local_ip = _get_local_ip()
    print(f"\n🌐 Personal Assistant Web 已启动")
    print(f"   本机访问: http://127.0.0.1:{port}")
    print(f"   局域网访问: http://{local_ip}:{port}")
    print(f"   手机扫码: http://{local_ip}:{port}/mobile\n")
    uvicorn.run(
        "personal_assistant.web:app",
        host=host,
        port=port,
        reload=True,
        ws_ping_interval=30,   # 每 30 秒发送 ping（默认 20 秒，Windows 本地容易超时）
        ws_ping_timeout=60,    # ping 超时 60 秒才断开（默认 60 秒）
    )


if __name__ == "__main__":
    main()
