"""埋点。写 SQLite，供结算屏、北极星指标和评测报告读取。

埋的不是"聊天记录"，而是 PRD 里定义的核心数据资产 ——
纠错轨迹 (Pedagogical Trace)：[玩家原句] → [路由判定] → [结构化纠错] → [人设化反馈] → [状态结算]。
一行一轮，字段齐全，才能事后回答"玩家是被什么劝退的"。
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from config import DATA_DIR

_LOCK = threading.Lock()
_DB_PATH = DATA_DIR / "telemetry.db"
_conn: sqlite3.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL    NOT NULL,
    session_id  TEXT    NOT NULL,
    scene_id    TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,
    turn_index  INTEGER,
    payload     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """幂等迁移。开发期的对局数据是真实数据，不能因为加字段就重建库。

    player_id 是后加的：早期只有 session_id，所以算不出次日留存 ——
    而次日留存正是 PRD 里假设二的判据。老数据的这一列会是 NULL，
    留存计算必须把 NULL 当"未知玩家"排除掉，不能当成同一个人。
    """
    have = {row["name"] for row in conn.execute("PRAGMA table_info(events)")}
    if "player_id" not in have:
        conn.execute("ALTER TABLE events ADD COLUMN player_id TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_player ON events(player_id)")
    conn.commit()


def db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA)
        _conn.commit()
        _migrate(_conn)
    return _conn


def log(
    session_id: str,
    scene_id: str,
    event_type: str,
    payload: dict,
    turn_index: int | None = None,
    player_id: str | None = None,
) -> None:
    conn = db()
    with _LOCK:
        conn.execute(
            "INSERT INTO events (ts, session_id, scene_id, event_type, turn_index, payload, player_id)"
            " VALUES (?,?,?,?,?,?,?)",
            (time.time(), session_id, scene_id, event_type, turn_index,
             json.dumps(payload, ensure_ascii=False), player_id),
        )
        conn.commit()


def db_path() -> Path:
    return _DB_PATH


# ------------------------------------------------------------------ 读取侧
def north_star() -> dict:
    """★ 北极星：单局主动目标语言输出量。以及验证 PRD 里三个假设需要的对照数据。"""
    conn = db()
    rows = [json.loads(r["payload"]) for r in conn.execute(
        "SELECT payload FROM events WHERE event_type='session_end' ORDER BY ts"
    )]
    if not rows:
        return {"sessions": 0, "note": "还没有已结束的对局"}

    def avg(key: str) -> float:
        vals = [r.get(key, 0) or 0 for r in rows]
        return round(sum(vals) / len(vals), 2)

    corrected = [r for r in rows if (r.get("corrections_shown") or 0) > 0]
    clean = [r for r in rows if not (r.get("corrections_shown") or 0)]

    return {
        "sessions": len(rows),
        # ★ 北极星指标
        "avg_target_words_per_session": avg("target_words_total"),
        "avg_target_words_per_turn": avg("target_words_per_turn"),
        "avg_target_language_ratio": avg("target_language_ratio"),
        "avg_turns": avg("turns"),
        "avg_duration_sec": avg("duration_sec"),
        # 假设二：被频繁纠错的玩家是不是玩得更短？（Glitch 惩罚是否过重）
        "hypothesis_correction_tolerance": {
            "sessions_with_corrections": len(corrected),
            "avg_turns_with_corrections": round(sum(r.get("turns", 0) for r in corrected) / len(corrected), 2) if corrected else None,
            "avg_turns_without_corrections": round(sum(r.get("turns", 0) for r in clean) / len(clean), 2) if clean else None,
        },
        "outcomes": {
            status: sum(1 for r in rows if r.get("status") == status)
            for status in {r.get("status", "unknown") for r in rows}
        },
    }


def retention() -> dict:
    """假设二的原始判据：被频繁纠错的玩家，次日还回来吗？

    此前因为埋点里没有 player_id，这条判据被迫降级成了"同一局的平均轮次" ——
    那只能看到"当场被劝退"，看不到"第二天不来了"。现在按 player_id 算真正的次日留存。

    口径写死在这里，不是等数据出来再挑一个：
      分组 —— 玩家的**第一局**是否触发过纠错（corrections_shown > 0）
      回访 —— 该玩家是否存在与首局不在同一自然日的另一局
    只有 player_id 非空的对局参与计算：老数据那一列是 NULL，
    把它们混进来会把不同的人当成同一个人。
    """
    conn = db()
    rows = list(conn.execute(
        "SELECT ts, player_id, payload FROM events"
        " WHERE event_type='session_end' AND player_id IS NOT NULL AND player_id != 'anonymous'"
        " ORDER BY ts"
    ))
    by_player: dict[str, list[tuple[float, dict]]] = {}
    for r in rows:
        by_player.setdefault(r["player_id"], []).append((r["ts"], json.loads(r["payload"])))

    groups = {"with_corrections": {"players": 0, "returned": 0},
              "without_corrections": {"players": 0, "returned": 0}}
    for sessions in by_player.values():
        first_ts, first = sessions[0]
        key = "with_corrections" if (first.get("corrections_shown") or 0) > 0 else "without_corrections"
        groups[key]["players"] += 1
        first_day = int(first_ts // 86400)
        if any(int(ts // 86400) != first_day for ts, _ in sessions):
            groups[key]["returned"] += 1

    for g in groups.values():
        g["return_rate"] = round(g["returned"] / g["players"], 3) if g["players"] else None

    total = sum(g["players"] for g in groups.values())
    return {
        "players": total,
        "sessions": len(rows),
        # 样本不足时不给结论 —— 两组各自至少 5 人才谈得上比较
        "conclusive": all(g["players"] >= 5 for g in groups.values()),
        **groups,
    }


def variant_stats() -> dict:
    """假设三：像素箱庭的 ROI。对比 diorama 与 text_only 的 session 时长与北极星。"""
    conn = db()
    rows = [json.loads(r["payload"]) for r in conn.execute(
        "SELECT payload FROM events WHERE event_type='session_end' ORDER BY ts"
    )]
    out: dict[str, dict] = {}
    for variant in ("diorama", "text_only"):
        group = [r for r in rows if r.get("variant") == variant]
        if not group:
            out[variant] = {"sessions": 0}
            continue
        out[variant] = {
            "sessions": len(group),
            "avg_duration_sec": round(sum(r.get("duration_sec", 0) for r in group) / len(group), 1),
            "avg_turns": round(sum(r.get("turns", 0) for r in group) / len(group), 2),
            "avg_target_words": round(sum(r.get("target_words_total", 0) for r in group) / len(group), 2),
        }
    out["conclusive"] = all(out[v].get("sessions", 0) >= 5 for v in ("diorama", "text_only"))
    return out


def routing_stats() -> dict:
    """假设一：Router 拦截率。PRD 的判定标准是低于 90% 就说明解耦不划算。"""
    conn = db()
    rows = [json.loads(r["payload"]) for r in conn.execute(
        "SELECT payload FROM events WHERE event_type='turn'"
    )]
    if not rows:
        return {"turns": 0}
    blocked = sum(1 for r in rows if not r.get("route", {}).get("in_scope", True))
    return {
        "turns": len(rows),
        "out_of_scope_turns": blocked,
        "out_of_scope_rate": round(blocked / len(rows), 3),
        "severity_mix": {
            level: sum(1 for r in rows if r.get("pedagogy", {}).get("severity") == level)
            for level in ("none", "minor", "major")
        },
    }
