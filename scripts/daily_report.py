"""每天看一眼：内测期的北极星与健康度日报。

替代 docs/deploy.md 里原本那三条手敲 shell。刻意不 import backend ——
运维环境只要有 python 就能跑，不需要装 fastapi，也不会因为 import 链
把服务的配置副作用带进来。

自然日按 UTC 切，与 limits 的额度口径一致（limits.py 用 ts % 86400）。

用法：
    python scripts/daily_report.py            # 最近 7 天
    python scripts/daily_report.py --days 30
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "telemetry.db"

DAILY_TURN_BUDGET = 2000   # 与 config.Limits 的默认值一致，仅用于显示水位


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _fmt(value) -> str:
    return "—" if value is None else str(value)


def collect(conn: sqlite3.Connection) -> dict[str, dict]:
    """按 UTC 自然日汇总。返回 {日期: 指标}。"""
    days: dict[str, dict] = defaultdict(lambda: {
        "sessions": 0, "players": set(), "wins": 0, "words": [], "turns": [],
        "turn_rows": 0, "feedback": [], "arms": defaultdict(list),
    })

    for ts, payload in conn.execute(
            "SELECT ts, payload FROM events WHERE event_type='session_end' ORDER BY ts"):
        d = days[_day(ts)]
        s = json.loads(payload)
        d["sessions"] += 1
        if s.get("player_id") and s["player_id"] != "anonymous":
            d["players"].add(s["player_id"])
        if s.get("status") == "won":
            d["wins"] += 1
        d["words"].append(s.get("target_words_total", 0) or 0)
        d["turns"].append(s.get("turns", 0) or 0)
        if s.get("variant"):
            d["arms"][s["variant"]].append(s.get("target_words_total", 0) or 0)

    for (ts,) in conn.execute("SELECT ts FROM events WHERE event_type='turn'"):
        days[_day(ts)]["turn_rows"] += 1

    for ts, payload in conn.execute(
            "SELECT ts, payload FROM events WHERE event_type='client_feedback'"):
        stars = json.loads(payload).get("stars")
        if isinstance(stars, (int, float)):
            days[_day(ts)]["feedback"].append(stars)

    return days


def retention_d1(conn: sqlite3.Connection) -> dict:
    """次日留存（假设二的判据）：首局触发过纠错的玩家，是否还有第二天的局。

    只认非空且非 anonymous 的 player_id —— 老数据那一列是 NULL，
    混进来会把不同的人当成同一个人。
    """
    by_player: dict[str, list[tuple[float, dict]]] = defaultdict(list)
    for ts, player_id, payload in conn.execute(
            "SELECT ts, player_id, payload FROM events WHERE event_type='session_end'"
            " AND player_id IS NOT NULL AND player_id != 'anonymous' ORDER BY ts"):
        by_player[player_id].append((ts, json.loads(payload)))

    groups = {"有纠错": [0, 0], "无纠错": [0, 0]}
    for sessions in by_player.values():
        first_ts, first = sessions[0]
        key = "有纠错" if (first.get("corrections_shown") or 0) > 0 else "无纠错"
        groups[key][0] += 1
        if any(_day(ts) != _day(first_ts) for ts, _ in sessions):
            groups[key][1] += 1
    return groups


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"埋点库不存在：{db_path}")
        return 1
    conn = sqlite3.connect(db_path)

    days = collect(conn)
    if not days:
        print("库里还没有已结束的对局。")
        return 0

    print(f"AlienLearn 日报 · {db_path}")
    print(f"（UTC 自然日，与额度口径一致；★ 北极星 = 单局主动输出的目标语言词数）\n")
    print(f"{'日期':12s}{'局数':>5s}{'玩家':>5s}{'胜率':>7s}{'★词/局':>9s}"
          f"{'轮/局':>7s}{'turn额度':>10s}{'反馈':>10s}")
    print("-" * 66)

    for date in sorted(days)[-args.days:]:
        d = days[date]
        win_rate = f"{d['wins'] / d['sessions']:.0%}" if d["sessions"] else "—"
        fb = f"{len(d['feedback'])}条 {_avg(d['feedback'])}★" if d["feedback"] else "—"
        budget = f"{d['turn_rows']}/{DAILY_TURN_BUDGET}"
        print(f"{date:12s}{d['sessions']:>5d}{len(d['players']):>5d}{win_rate:>7s}"
              f"{_fmt(_avg(d['words'])):>9s}{_fmt(_avg(d['turns'])):>7s}{budget:>10s}{fb:>10s}")

    # A/B（假设三：像素箱庭的 ROI）
    arms: dict[str, list[int]] = defaultdict(list)
    for d in days.values():
        for arm, words in d["arms"].items():
            arms[arm].extend(words)
    print("\nA/B 两臂（★词/局）：", end="")
    if arms:
        parts = [f"{arm} {len(v)}局 {_fmt(_avg(v))}词" for arm, v in sorted(arms.items())]
        enough = all(len(arms.get(a, [])) >= 5 for a in ("diorama", "text_only"))
        print("  ".join(parts) + ("" if enough else "   ← 样本不足 5 局/臂，先别下结论"))
    else:
        print("—")

    print("次日留存（假设二）：", end="")
    groups = retention_d1(conn)
    parts = []
    for name, (players, returned) in groups.items():
        rate = f"{returned / players:.0%}" if players else "—"
        parts.append(f"{name} {returned}/{players} ({rate})")
    enough = all(p >= 5 for p, _ in groups.values())
    print("  ".join(parts) + ("" if enough else "   ← 样本不足 5 人/组，先别下结论"))

    # 内测期自查：写入闸是否还在生效（评测流量不该出现在库里）
    leaked = conn.execute(
        "SELECT COUNT(DISTINCT session_id) FROM events WHERE"
        " player_id LIKE 'e2e\\_%' ESCAPE '\\' OR player_id LIKE 'smoke\\_%' ESCAPE '\\'"
        " OR player_id LIKE 'live\\_%' ESCAPE '\\' OR player_id LIKE 'diag\\_%' ESCAPE '\\'"
    ).fetchone()[0]
    if leaked:
        print(f"\n⚠ 库里有 {leaked} 个自测会话漏进来了 —— 检查写入闸（game_state.channel_for）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
