"""清洗判据：哪些 session 是测试/评测残渣。

这些判据不是猜的，是从真库里反查出来的形态（见 evidence-07）：
  - 评测跑的局不走 /api/session，所以没有 session_start
  - redteam 的 forced_continue 会让同一个 session 反复写 session_end（实测最多 46 条）
  - 手工自测局的 player_id 带下划线前缀（真实玩家是无分隔符 UUID）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import telemetry
from purge_telemetry import select_purge_sessions


def _seed() -> None:
    # 干净的真实局：有 session_start，一条 session_end，UUID 形态的 player_id
    telemetry.log("clean1", "ramen_en", "session_start", {}, player_id="a3f9c1d24b8e")
    telemetry.log("clean1", "ramen_en", "turn", {}, player_id="a3f9c1d24b8e")
    telemetry.log("clean1", "ramen_en", "session_end", {"status": "won"}, player_id="a3f9c1d24b8e")

    # 判据一：没有 session_start（进程内直调 orchestrator 的评测局）
    telemetry.log("noStart", "ramen_en", "turn", {}, player_id="anonymous")
    telemetry.log("noStart", "ramen_en", "session_end", {}, player_id="anonymous")

    # 判据二：多条 session_end（redteam 的 forced_continue）
    telemetry.log("multiEnd", "ramen_en", "session_start", {}, player_id="b7e2")
    for _ in range(3):
        telemetry.log("multiEnd", "ramen_en", "session_end", {}, player_id="b7e2")

    # 判据三：前缀化 player_id 的手工自测局
    telemetry.log("e2e1", "ramen_en", "session_start", {}, player_id="e2e_stage3")
    telemetry.log("e2e1", "ramen_en", "session_end", {}, player_id="e2e_stage3")


def test_each_criterion_selects_its_own_sessions():
    _seed()
    buckets = select_purge_sessions(telemetry.db())
    assert buckets["no_session_start"] == {"noStart"}
    assert buckets["multiple_session_end"] == {"multiEnd"}
    assert buckets["eval_player_id"] == {"e2e1"}


def test_clean_session_survives_every_criterion():
    _seed()
    buckets = select_purge_sessions(telemetry.db())
    assert not any("clean1" in ids for ids in buckets.values())


def test_empty_db_selects_nothing():
    buckets = select_purge_sessions(telemetry.db())
    assert all(ids == set() for ids in buckets.values())
