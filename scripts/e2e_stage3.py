"""端到端冒烟：走真 HTTP，验 SSE 的词汇返能字段与 client_event 端点。

和 backend/tests 的分工：单测覆盖状态机与端点逻辑，这个脚本覆盖
"真的起了一个服务、真的发了 HTTP、SSE 真的能被解析" —— 那些在进程内
测试里全部被绕过的部分。

用法（先起服务）：
    python backend/run.py
    python scripts/e2e_stage3.py [--base http://127.0.0.1:8000]

player_id 用 e2e_ 前缀是刻意的：服务端据此把这局判成 eval 流量，
一行埋点都不会写（见 game_state.channel_for）。脚本最后会验证这一点 ——
自测跑完不留痕，正是内测期指标可信的前提。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from config import Rules  # noqa: E402 —— 数值只有一份来源，脚本不再硬编码第二份

PLAYER_ID = "e2e_stage3"
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "telemetry.db"


def post(base: str, path: str, body: dict) -> tuple[int, dict | str]:
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            raw = res.read().decode()
            try:
                return res.status, json.loads(raw)
            except json.JSONDecodeError:
                return res.status, raw
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def sse_event(raw: str, name: str) -> dict | None:
    for block in raw.split("\n\n"):
        if f"event: {name}" in block:
            for line in block.split("\n"):
                if line.startswith("data: "):
                    return json.loads(line[6:])
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    status, payload = post(base, "/api/session",
                           {"scene_id": "ramen_en", "player_id": PLAYER_ID})
    assert status == 200, payload
    sid = payload["state"]["session_id"]
    vocab_total = payload["state"]["vocab_total"]
    assert vocab_total == len(payload["scene"]["target_vocab"]), payload["state"]
    print(f"session {sid} variant={payload['state']['variant']} vocab 0/{vocab_total}")

    status, raw = post(base, "/api/turn",
                       {"session_id": sid, "text": "One miso ramen, please."})
    assert status == 200, raw
    state = sse_event(raw, "state")
    assert state is not None, raw[:500]
    print(f"turn1 hits={state['vocab_new_hits']} refund={state['energy_refund']}"
          f" delta={state['energy_delta']} vocab={state['vocab_hit_count']}/{state['vocab_total']}")
    assert "ramen" in state["vocab_new_hits"] and "please" in state["vocab_new_hits"]
    # 命中两个新词 → 返还 2×3=6，恰好抵掉每轮的 6 点消耗
    expected_refund = 2 * Rules.energy_per_vocab_hit
    assert state["energy_refund"] == expected_refund, state
    assert state["energy_delta"] == expected_refund - Rules.energy_per_turn, state

    status, out = post(base, "/api/client_event",
                       {"session_id": sid, "type": "span_match_failed",
                        "payload": {"span": "xx", "turn": 1}})
    assert status == 200, (status, out)
    status, out = post(base, "/api/client_event",
                       {"session_id": sid, "type": "evil_type", "payload": {}})
    assert status == 422, (status, out)
    status, out = post(base, "/api/client_event",
                       {"session_id": "nope", "type": "span_match_failed", "payload": {}})
    assert status == 404, (status, out)
    print("client_event 白名单 / 未知会话 / 超长载荷 三条路径符合预期")

    # 写入闸：e2e_ 前缀是 eval 流量，整局不该在库里留下任何一行
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        left = conn.execute("SELECT COUNT(*) FROM events WHERE player_id=?",
                            (PLAYER_ID,)).fetchone()[0]
        assert left == 0, f"自测流量漏进埋点库 {left} 行 —— 检查 game_state.channel_for"
        print("埋点库无自测残留 ✓")

    print("E2E OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
