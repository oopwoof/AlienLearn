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


def db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


def log(session_id: str, scene_id: str, event_type: str, payload: dict, turn_index: int | None = None) -> None:
    conn = db()
    with _LOCK:
        conn.execute(
            "INSERT INTO events (ts, session_id, scene_id, event_type, turn_index, payload) VALUES (?,?,?,?,?,?)",
            (time.time(), session_id, scene_id, event_type, turn_index, json.dumps(payload, ensure_ascii=False)),
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
