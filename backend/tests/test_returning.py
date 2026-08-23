"""NPC 认出回头客。

服务假设二（次日留存）：给回来的人一个"这里记得你"的信号。刻意做得很轻——
NPC 只是觉得眼熟，不假装记得上一局说过什么。让 LLM"回忆"没有存过的细节
就是让它编，而编出来的假记忆比不记得更破坏可信度。
"""

import agents
import telemetry
from config import load_scene
from game_state import STORE


def _start(player_id: str, scene_id: str = "ramen_en") -> None:
    telemetry.log("s" + str(id(player_id)), scene_id, "session_start", {}, player_id=player_id)


def test_scene_visits_counts_only_this_scene():
    for _ in range(2):
        telemetry.log("a", "ramen_en", "session_start", {}, player_id="p1")
    telemetry.log("b", "flower_en", "session_start", {}, player_id="p1")
    telemetry.log("c", "ramen_en", "session_start", {}, player_id="p2")

    assert telemetry.scene_visits("p1", "ramen_en") == 2
    assert telemetry.scene_visits("p1", "flower_en") == 1
    assert telemetry.scene_visits("p1", "bookshop_en") == 0


def test_anonymous_is_never_a_returning_customer():
    """anonymous 是所有隐私模式玩家共用的 id —— 认它等于把陌生人当熟客。"""
    for _ in range(5):
        telemetry.log("x", "ramen_en", "session_start", {}, player_id="anonymous")
    assert telemetry.scene_visits("anonymous", "ramen_en") == 0


def test_store_create_records_visits():
    telemetry.log("a", "ramen_en", "session_start", {}, player_id="p9")
    session = STORE.create(load_scene("ramen_en"), player_id="p9")
    assert session.visits == 1
    assert STORE.create(load_scene("ramen_en"), player_id="newbie").visits == 0


def test_persona_prompt_mentions_returning_only_when_visited():
    scene = load_scene("ramen_en")
    stage = scene["quest"]["stages"][0]
    first = agents._persona_system(scene, stage, False, visits=0)
    again = agents._persona_system(scene, stage, False, visits=2)
    assert "眼熟" not in first
    assert "眼熟" in again
    # 不许把"记得上次聊了什么"写进 prompt —— 那是让模型编造
    assert "上次" not in again and "上一局" not in again
