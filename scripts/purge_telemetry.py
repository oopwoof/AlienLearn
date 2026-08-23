"""从埋点库里清掉测试与评测残渣。默认只看不删。

为什么需要这个：开发期的自测局和评测跑批都写进了同一个库，而
`north_star()` 对 session_end 不做任何过滤 —— 实测 204 条 session_end
对 30 条 session_start，北极星算的基本是评测局的平均值。内测第一位
玩家进来之前必须清一次，否则真实数据会被埋在残渣里。

（写入侧的闸已经在 `game_state.channel_for` / orchestrator 补上了，
新的评测流量不再落库。这个脚本只处理历史遗留。）

用法：
    python scripts/purge_telemetry.py             # 只报告命中，不动数据
    python scripts/purge_telemetry.py --execute   # 备份后删除

三条判据都指向"这不是真人玩的一局"，且互相独立（一个 session 可能同时命中多条）：
  no_session_start      没有 session_start —— 评测直调 orchestrator，不走 /api/session
  multiple_session_end  多条 session_end —— redteam 的 forced_continue 让一个会话反复结束
  eval_player_id        player_id 带自测前缀 —— e2e_/smoke_/live_/diag_/rl_/budget_
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "telemetry.db"

# 与 backend/game_state.EVAL_PLAYER_PREFIXES 同一张表。刻意复制而不是 import：
# 这个脚本要能在没装 fastapi 的运维环境里跑（改动时两边一起改）
EVAL_PLAYER_PREFIXES = ("e2e_", "smoke_", "live_", "diag_", "rl_", "budget_")


def select_purge_sessions(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """三条判据各自命中的 session_id。纯查询，不改任何数据。"""
    all_sessions = {r[0] for r in conn.execute("SELECT DISTINCT session_id FROM events")}

    started = {r[0] for r in conn.execute(
        "SELECT DISTINCT session_id FROM events WHERE event_type='session_start'")}

    multi_end = {r[0] for r in conn.execute(
        "SELECT session_id FROM events WHERE event_type='session_end'"
        " GROUP BY session_id HAVING COUNT(*) > 1")}

    eval_ids: set[str] = set()
    for prefix in EVAL_PLAYER_PREFIXES:
        eval_ids |= {r[0] for r in conn.execute(
            "SELECT DISTINCT session_id FROM events WHERE player_id LIKE ?", (prefix + "%",))}

    return {
        "no_session_start": all_sessions - started,
        "multiple_session_end": multi_end,
        "eval_player_id": eval_ids,
    }


def backup(conn: sqlite3.Connection) -> Path:
    """删之前先整库备份。用标准库的 backup()，不依赖 sqlite3 命令行 —— Windows 上未必有。"""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = DB_PATH.parent / f"backup-{stamp}.db"
    with sqlite3.connect(path) as dest:
        conn.backup(dest)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--execute", action="store_true",
                        help="真的删除（默认只报告）")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"埋点库不存在：{db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    total_rows = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    total_sessions = conn.execute("SELECT COUNT(DISTINCT session_id) FROM events").fetchone()[0]

    buckets = select_purge_sessions(conn)
    doomed: set[str] = set()
    print(f"库：{db_path}")
    print(f"现有 {total_rows} 行 / {total_sessions} 个会话\n")
    for name, ids in buckets.items():
        print(f"  {name:22s} 命中 {len(ids):4d} 个会话")
        doomed |= ids

    rows_doomed = 0
    if doomed:
        marks = ",".join("?" * len(doomed))
        rows_doomed = conn.execute(
            f"SELECT COUNT(*) FROM events WHERE session_id IN ({marks})", tuple(doomed)
        ).fetchone()[0]

    kept_sessions = total_sessions - len(doomed)
    print(f"\n合计待删 {len(doomed)} 个会话 / {rows_doomed} 行"
          f"（保留 {kept_sessions} 个会话 / {total_rows - rows_doomed} 行）")

    if not args.execute:
        print("\n这是预演。确认无误后加 --execute 执行。")
        return 0

    if not doomed:
        print("没有需要删除的会话。")
        return 0

    saved = backup(conn)
    print(f"\n已备份到 {saved}")
    marks = ",".join("?" * len(doomed))
    conn.execute(f"DELETE FROM events WHERE session_id IN ({marks})", tuple(doomed))
    conn.commit()
    conn.execute("VACUUM")
    left_rows = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    left_sessions = conn.execute("SELECT COUNT(DISTINCT session_id) FROM events").fetchone()[0]
    print(f"已删除。现在 {left_rows} 行 / {left_sessions} 个会话")
    return 0


if __name__ == "__main__":
    sys.exit(main())
