"""埋点写入闸：只有真实玩家的对局才进库。

为什么需要这道闸（两个都是实际发生过的问题）：
  1. `eval/redteam.py` 直接调 orchestrator 跑套件，每轮都写 turn 埋点 ——
     204 条 session_end 里绝大多数是评测残渣，北极星算的是评测局的平均值。
  2. 日额度 `limits._turns_today()` 数的就是 turn 事件行数，所以跑一次评测
     会吃掉玩家几十上百轮的预算。

channel 只能由服务端决定：进程内构造时传参，HTTP 路径按 player_id 前缀映射。
**绝不能让客户端自报** —— 不写 turn 行等于不计额度，自报就是白嫖 LLM 预算的口子。
"""

import asyncio

import limits
import orchestrator
import telemetry
from config import load_scene
from game_state import STORE, Session


def make_scene() -> dict:
    # 用真场景而不是 stub：orchestrator 会一路走到 Agent 层，
    # 规则桩也需要 npc/quest/target_vocab 这些字段齐全
    return load_scene("ramen_en")


def _rows(event_type: str | None = None) -> list:
    sql = "SELECT * FROM events"
    args: tuple = ()
    if event_type:
        sql += " WHERE event_type=?"
        args = (event_type,)
    return list(telemetry.db().execute(sql, args))


def _run(session: Session, text: str) -> list[tuple[str, dict]]:
    async def go():
        return [(event, payload) async for event, payload in orchestrator.run_turn(session, text)]

    return asyncio.run(go())


def test_player_channel_writes_turn_events():
    session = Session(scene=make_scene())
    assert session.channel == "player"
    _run(session, "One miso ramen, please.")
    assert len(_rows("turn")) == 1


def test_eval_channel_writes_nothing():
    session = Session(scene=make_scene(), channel="eval")
    _run(session, "One miso ramen, please.")
    assert _rows() == []


def test_eval_channel_does_not_consume_daily_budget(monkeypatch):
    """评测轮次不该挤占玩家的日额度 —— 额度是数 turn 行算的。"""
    monkeypatch.setattr(limits, "_budget_cache", (0.0, 0))
    session = Session(scene=make_scene(), channel="eval")
    for _ in range(3):
        _run(session, "One miso ramen, please.")
        monkeypatch.setattr(limits, "_budget_cache", (0.0, 0))  # 绕开 20s 缓存，强制回源
    assert limits._turns_today() == 0


def test_eval_channel_skips_session_end_too():
    session = Session(scene=make_scene(), channel="eval")
    session.energy = 1          # 下一轮必定 drained，触发 session_end 分支
    # 刻意不带目标词：命中新词会返能（+3/词），能量就掉不到 0
    events = _run(session, "Yes, of course.")
    assert any(kind == "ended" for kind, _ in events)   # 事件流照常，只是不落库
    assert _rows("session_end") == []


def test_store_create_maps_eval_player_prefixes_to_eval_channel():
    """e2e_/smoke_/live_/diag_ 这些是手工测试脚本用的 player_id，
    真实玩家的 id 是无分隔符的 UUID，撞不上。"""
    for player_id in ("e2e_stage3", "smoke_flower", "live_ramen_check", "diag_signal",
                      "rl_e2e", "budget_e2e"):
        session = STORE.create(make_scene(), player_id=player_id)
        assert session.channel == "eval", player_id


def test_store_create_keeps_real_players_on_player_channel():
    session = STORE.create(make_scene(), player_id="a3f9c1d24b8e4f77a1c2")
    assert session.channel == "player"
    # anonymous 是隐私模式下的真实玩家（localStorage 不可写），不能当评测流量丢掉
    assert STORE.create(make_scene(), player_id="anonymous").channel == "player"
