"""一轮对话的编排。

    玩家输入
       │
       ▼
    Router Agent ──── in_scope? ────┐
       │                            │
       ├──────────────┬─────────────┘
       ▼              ▼
  Pedagogy Agent   Persona Agent（流式）        ← 这两个并行，首字延迟只等 Router
    (JSON纠错)      (台词 + 结构化信号)
       │              │
       └──────┬───────┘
              ▼
      状态机结算（伪装度 / 能量 / 阶段 / 崩溃）  ← 纯 Python，不让 LLM 碰数值
              ▼
        埋点写库 + SSE 推前端

事件顺序：route → (pedagogy 就绪即发) → npc_delta* → npc_signal → state → done
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import agents
import telemetry
from game_state import Session


async def run_turn(session: Session, text: str) -> AsyncIterator[tuple[str, dict]]:
    scene = session.scene
    stage = session.stage
    stage_id_before = stage["id"]

    # ---- 1. Router 先行：Persona 的行为分支（正常演出 vs 挡回去）取决于它
    route_result = await agents.route(text, scene, stage_id_before)
    yield "route", route_result
    in_scope = route_result["in_scope"]

    # ---- 2. Pedagogy 与 Persona 并行
    ped_task = asyncio.create_task(agents.assess(text, scene))

    # mock 模式下规则桩是瞬时的，直接取来喂给 Persona 桩（live 模式不需要，模型自己会觉得话怪）
    has_error = False
    if not agents.CLIENT.live:
        pedagogy_peek = await ped_task
        has_error = pedagogy_peek["severity"] in {"minor", "major"}

    npc_parts: list[str] = []
    signal = dict(agents.DEFAULT_SIGNAL)
    pedagogy: dict | None = None

    stream = agents.perform(
        scene,
        stage,
        session.recent_history(),
        text,
        in_scope=in_scope,
        secret_unlocked=session.secret_unlocked,
        has_error=has_error,
    )

    async for kind, payload in stream:
        if kind == "delta":
            npc_parts.append(str(payload))
            yield "npc_delta", {"text": payload}
        else:
            signal = payload  # type: ignore[assignment]

        # 纠错数据流一就绪就推给 HUD —— 玩家会看到它在 NPC 说话时静默滑出
        if pedagogy is None and ped_task.done():
            pedagogy = ped_task.result()
            yield "pedagogy", pedagogy

    if pedagogy is None:
        pedagogy = await ped_task
        yield "pedagogy", pedagogy

    yield "npc_signal", signal

    npc_text = "".join(npc_parts).strip()

    # ---- 3. 状态机结算
    outcome = session.settle(
        in_scope=in_scope,
        severity=pedagogy["severity"],
        used_target_language=pedagogy["used_target_language"],
        target_words=pedagogy["target_word_count"],
        quest_signal=signal["quest_signal"],
        revealed_secret=bool(signal.get("revealed_secret")),
    )
    if pedagogy["errors"]:
        session.corrections_shown += 1

    session.remember("player", text)
    session.remember("npc", npc_text)

    state = session.public_state()
    state["emotion"] = signal["emotion"]
    state["stage_advanced"] = outcome.stage_advanced
    state["suspicion_delta"] = outcome.suspicion_delta
    state["reasons"] = outcome.reasons
    yield "state", state

    # ---- 4. 埋点：一行一轮的完整纠错轨迹
    telemetry.log(
        session.session_id,
        scene["scene_id"],
        "turn",
        {
            "player_text": text,
            "stage_before": stage_id_before,
            "stage_after": outcome.stage_id,
            "route": route_result,
            "pedagogy": pedagogy,
            "npc_text": npc_text,
            "signal": signal,
            "suspicion_before": outcome.suspicion_before,
            "suspicion_after": outcome.suspicion_after,
            "suspicion_delta": outcome.suspicion_delta,
            "glitch_level": outcome.glitch_level,
            "energy": outcome.energy,
            "status": outcome.status,
            "llm_mode": agents.CLIENT.mode,
        },
        turn_index=session.turn_count,
    )

    if session.status != "playing":
        summary = session.summary()
        telemetry.log(session.session_id, scene["scene_id"], "session_end", summary)
        ending = {
            "won": scene["victory_line"],
            "crashed": scene["crash_line"],
            "drained": "全息能量耗尽。碎片把你温柔地推了出去 —— 今晚的雨你只淋了一半。",
        }.get(session.status, "")
        yield "ended", {"status": session.status, "line": ending, "summary": summary}

    yield "done", {}
