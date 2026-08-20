"""FastAPI 入口。一条命令启动：

    python -m uvicorn main:app --reload --app-dir backend
或  python backend/run.py
"""

from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import limits
import orchestrator
import telemetry
from agents import CLIENT
from config import FRONTEND_DIR, SETTINGS, list_scenes, load_scene
from game_state import STORE

@asynccontextmanager
async def lifespan(_: FastAPI):
    telemetry.db()
    print(f"[AlienLearn] LLM 模式: {CLIENT.mode}" + ("" if CLIENT.live else "（规则桩，无需 API key）"))
    print(f"[AlienLearn] 埋点库: {telemetry.db_path()}")
    yield


app = FastAPI(title="AlienLearn MVP", version="0.1.0", lifespan=lifespan)


class NewSession(BaseModel):
    scene_id: str = Field(default_factory=lambda: SETTINGS.default_scene)
    # 前端 localStorage 里的匿名 UUID。不是账号，不含任何个人信息 ——
    # 它唯一的用途是把同一个人的多局串起来，好算次日留存（假设二的原始判据）。
    # 收窄长度是为了别让它变成一个可以往里塞任意数据的字段。
    player_id: str = Field(default="anonymous", max_length=64)


class TurnInput(BaseModel):
    session_id: str
    text: str


class ClientEvent(BaseModel):
    """前端上报的埋点。存在的理由：手机内测者不会开控制台 ——
    只 console.warn 的前端故障（比如 span 高亮匹配失败）等于没发生。"""

    session_id: str
    type: str = Field(max_length=40)
    payload: dict = Field(default_factory=dict)


# 白名单：前端能写进埋点库的事件类型。防止这个端点变成任意数据的倾倒口
_CLIENT_EVENT_TYPES = {"span_match_failed"}


# ------------------------------------------------------------------ 元信息
@app.get("/api/meta")
def meta() -> dict:
    return {
        "llm_mode": CLIENT.mode,
        "model": SETTINGS.model if CLIENT.live else "mock-rules",
        "scenes": list_scenes(),
        "default_scene": SETTINGS.default_scene,
    }


# ------------------------------------------------------------------ 开一局
@app.post("/api/session")
def create_session(body: NewSession) -> dict:
    try:
        scene = load_scene(body.scene_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    session = STORE.create(scene, player_id=body.player_id)
    telemetry.log(
        session.session_id,
        scene["scene_id"],
        "session_start",
        {
            "llm_mode": CLIENT.mode,
            "target_language": scene["target_language"],
            "player_id": session.player_id,
            "variant": session.variant,
        },
        player_id=session.player_id,
    )
    return {
        "state": session.public_state(),
        "scene": {
            "scene_id": scene["scene_id"],
            "display_name": scene["display_name"],
            "fragment_code": scene["fragment_code"],
            "target_language": scene["target_language"],
            "target_language_label": scene["target_language_label"],
            "cefr_level": scene["cefr_level"],
            "intro": scene["intro"],
            "mask": scene["mask"],
            "npc_name": scene["npc"]["name"],
            "npc_title": scene["npc"]["title"],
            "quest": {
                "title": scene["quest"]["title"],
                "objectives": scene["quest"]["objectives"],
                "stages": [
                    {"id": s["id"], "name": s["name"], "hud_label": s["hud_label"]}
                    for s in scene["quest"]["stages"]
                ],
            },
            "target_vocab": scene["target_vocab"],
            "art": scene.get("art", "ramen"),
            "opening_line": scene["opening_line"],
            "opening_stage_directions": scene["opening_stage_directions"],
        },
        "llm_mode": CLIENT.mode,
    }


@app.get("/api/player/{player_id}/stats")
def player_stats(player_id: str) -> dict:
    # player_id 是前端 localStorage 里的 UUID（或 anonymous）。收窄字符集，
    # 别让路径参数变成能注入任意内容的口子
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", player_id):
        raise HTTPException(status_code=422, detail="非法的玩家标识")
    return telemetry.player_stats(player_id)


@app.get("/api/session/{session_id}/summary")
def session_summary(session_id: str) -> dict:
    session = STORE.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在（服务重启后内存态会清空）")
    return session.summary()


# ------------------------------------------------------------------ 一轮对话
def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/api/turn")
async def turn(body: TurnInput, request: Request) -> StreamingResponse:
    session = STORE.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.status != "playing":
        raise HTTPException(status_code=409, detail=f"本局已结束（{session.status}）")

    # 用量闸门。放在这里而不是 LLM 客户端里，是为了只约束玩家流量 ——
    # eval/ 下的批处理脚本不该被内测的额度限制误伤。
    client_ip = request.client.host if request.client else "unknown"
    blocked = limits.check_rate(session.player_id, client_ip)
    if blocked:
        raise HTTPException(status_code=429, detail=blocked)
    if limits.budget_exhausted():
        # 刻意选择「拒绝」而不是「降级到规则桩」：内测的全部目的是收集真实行为数据，
        # 悄悄把 NPC 换成规则桩会往数据集里灌垃圾 —— 那比让人今天玩不了更糟。
        telemetry.log(session.session_id, session.scene["scene_id"], "budget_exhausted",
                      limits.snapshot(), player_id=session.player_id)
        raise HTTPException(
            status_code=503,
            detail="今天的全息能量池已经见底了 —— 明天再来，碎片会还在这里。",
        )
    limits.note_turn()

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="不能发送空白输入")
    if len(text) > 600:
        raise HTTPException(status_code=422, detail="单轮输入过长（上限 600 字符）")

    async def stream() -> AsyncIterator[str]:
        try:
            async for event, payload in orchestrator.run_turn(session, text):
                yield _sse(event, payload)
        except Exception as exc:  # noqa: BLE001 — 任何异常都要让前端收到可读的收尾
            yield _sse("error", {"message": f"链路异常: {exc}"})
            yield _sse("done", {})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ------------------------------------------------------------------ 前端埋点
@app.post("/api/client_event")
def client_event(body: ClientEvent) -> dict:
    if body.type not in _CLIENT_EVENT_TYPES:
        raise HTTPException(status_code=422, detail="未知的前端事件类型")
    session = STORE.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    payload = body.payload
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > 2048:
        payload = {"truncated": True}
    telemetry.log(
        session.session_id,
        session.scene["scene_id"],
        f"client_{body.type}",
        payload,
        player_id=session.player_id,
    )
    return {"ok": True}


# ------------------------------------------------------------------ 指标
@app.get("/api/metrics")
def metrics() -> dict:
    return {
        "north_star": telemetry.north_star(),
        "routing": telemetry.routing_stats(),
        "retention": telemetry.retention(),      # 假设二
        "variants": telemetry.variant_stats(),   # 假设三
        "usage": limits.snapshot(),              # 运维：是不是撞了额度闸
    }


# ------------------------------------------------------------------ 前端托管
@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
