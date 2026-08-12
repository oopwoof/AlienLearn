"""用量闸门：防止一个泄漏的链接把 API 余额烧光。

这不是"限制玩家"，是**给成本装个保险丝**。设计上有两条原则：

1. **超额降级，不报错。** 日额度烧完时切到本地规则桩继续能玩，而不是把人挡在门外。
   代价是 NPC 变成规则桩 —— 所以必须让玩家看得见（状态轨会显示「链路 规则桩」），
   静默降级等于骗人。
2. **频率限制才返回拒绝。** 那是异常行为（脚本刷），不是正常玩家会撞到的。

单局本来已经被能量体系封在约 16 轮（`Rules.energy_per_turn`），这是第一道闸；
这里补的是"跨对局、跨玩家"的第二道闸。
"""

from __future__ import annotations

import math
import time
from collections import defaultdict, deque

import telemetry
from config import Limits

# 滑动窗口：{key: 最近若干次请求的时间戳}
_recent: dict[str, deque[float]] = defaultdict(deque)

# 日额度是查库算的，但不能每轮都查 —— 缓存住，最多每 N 秒回源一次
_budget_cache: tuple[float, int] = (0.0, 0)


def _turns_today() -> int:
    """今天已经消耗了多少轮真实模型调用。

    以本地自然日为界（和留存口径一致）。用埋点里的 turn 事件计数，
    好处是重启不丢、也不需要另建一张表。
    """
    global _budget_cache
    now = time.time()
    cached_at, value = _budget_cache
    if now - cached_at < Limits.budget_refresh_sec:
        return value

    day_start = now - (now % 86400)
    row = telemetry.db().execute(
        "SELECT COUNT(*) AS n FROM events WHERE event_type='turn' AND ts >= ?", (day_start,)
    ).fetchone()
    value = int(row["n"]) if row else 0
    _budget_cache = (now, value)
    return value


def budget_exhausted() -> bool:
    """今日额度是否已用尽。0 或负数表示不限额。"""
    if Limits.daily_turn_budget <= 0:
        return False
    return _turns_today() >= Limits.daily_turn_budget


def note_turn() -> None:
    """乐观地把缓存计数 +1，避免同一个刷新窗口内连续多轮都读到旧值。"""
    global _budget_cache
    cached_at, value = _budget_cache
    if cached_at:
        _budget_cache = (cached_at, value + 1)


def check_rate(player_id: str, ip: str) -> str | None:
    """频率限制。返回 None 表示放行，否则返回给玩家看的中文原因。

    按 player_id 和 IP 各自独立限流：只按 IP 会把同一个网络下的多个测试者
    误伤成一个人；只按 player_id 则清一下 localStorage 就绕过了。
    """
    now = time.time()
    for key, limit in (
        (f"p:{player_id}", Limits.turns_per_minute_per_player),
        (f"i:{ip}", Limits.turns_per_minute_per_ip),
    ):
        if limit <= 0:
            continue
        window = _recent[key]
        while window and now - window[0] > 60.0:
            window.popleft()
        if len(window) >= limit:
            # 用 ceil 而不是 int()+1：后者在窗口刚开始时会算出 61 秒，
            # 比 60 秒的窗口本身还长，读起来就是个错的数
            wait = max(1, math.ceil(60.0 - (now - window[0])))
            return f"说得太快了 —— 全息链路需要 {wait} 秒缓一下。"
        window.append(now)
    return None


def snapshot() -> dict:
    """给 /api/metrics 用的可观测数据。运维时要能看出是不是撞了闸。"""
    return {
        "turns_today": _turns_today(),
        "daily_turn_budget": Limits.daily_turn_budget,
        "budget_exhausted": budget_exhausted(),
    }
