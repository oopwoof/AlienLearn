"""场景可选字段的默认值约定：旧 JSON 一个字段不加也必须照常跑。"""

from config import secret_stage_id
from game_state import Session
from test_economy import clean_turn, make_scene


def test_secret_stage_defaults_to_last_stage():
    scene = make_scene()
    assert "secret_stage_id" not in scene
    assert secret_stage_id(scene) == "intel"


def test_secret_stage_explicit_override():
    scene = make_scene()
    scene["secret_stage_id"] = "order"
    assert secret_stage_id(scene) == "order"


def test_secret_unlocks_on_configured_stage():
    # 把秘密幕改到第二幕：到达并停留一轮后解锁，不再依赖写死的 "intel"
    scene = make_scene()
    scene["secret_stage_id"] = "order"
    s = Session(scene=scene)
    s.stage_index = 1  # 直接站上 order 幕
    assert not s.secret_unlocked
    clean_turn(s)      # 在秘密幕停留一轮
    assert s.secret_unlocked


def test_secret_does_not_unlock_elsewhere():
    scene = make_scene()
    scene["secret_stage_id"] = "order"
    s = Session(scene=scene)   # 还在 enter 幕
    clean_turn(s)
    clean_turn(s)
    assert not s.secret_unlocked
