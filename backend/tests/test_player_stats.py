"""跨局累计（player_stats）的口径测试：只认精确匹配的 player_id。"""

import telemetry


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "_DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(telemetry, "_conn", None)


def test_player_stats_aggregates_own_sessions_only(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    telemetry.log("s1", "ramen_en", "session_end",
                  {"status": "drained", "target_words_total": 30, "stage_index": 1}, player_id="p1")
    telemetry.log("s2", "ramen_en", "session_end",
                  {"status": "won", "target_words_total": 42, "stage_index": 3}, player_id="p1")
    telemetry.log("s3", "ramen_en", "session_end",
                  {"status": "won", "target_words_total": 99, "stage_index": 3}, player_id="p2")
    # player_id 为 NULL 的老数据：精确匹配天然排除，不能混进任何人的累计
    telemetry.log("s4", "ramen_en", "session_end",
                  {"status": "won", "target_words_total": 77, "stage_index": 3})

    stats = telemetry.player_stats("p1")
    assert stats == {
        "sessions": 2,
        "wins": 1,
        "total_target_words": 72,
        "best_words": 42,
        "best_stage_index": 3,
    }


def test_player_stats_unknown_player_returns_zeros(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    stats = telemetry.player_stats("ghost")
    assert stats["sessions"] == 0 and stats["best_words"] == 0
