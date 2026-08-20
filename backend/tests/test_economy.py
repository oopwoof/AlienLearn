"""能量-词汇经济的数值账本。

这些数值内测开始后即冻结（中途改数值会毁掉 A/B 与留存数据的可比性），
所以这里的断言就是账本本身：要改 Rules 里的数值，先改这里的推导注释。
"""

from config import Rules
from game_state import Session
from lang_utils import match_target_vocab

VOCAB = [
    "ramen", "bowl", "order", "seat", "rain", "soup", "broth",
    "hot", "delicious", "recipe", "secret", "tonight", "hungry", "please",
]


def make_scene() -> dict:
    return {
        "scene_id": "test_scene",
        "word_counting": "space",
        "target_vocab": list(VOCAB),
        "quest": {
            "stages": [
                {"id": "enter", "name": "进店"},
                {"id": "order", "name": "点单"},
                {"id": "smalltalk", "name": "闲聊"},
                {"id": "intel", "name": "情报"},
            ]
        },
    }


def clean_turn(session: Session, vocab_candidates=()):
    return session.settle(
        in_scope=True,
        severity="none",
        used_target_language=True,
        target_words=5,
        quest_signal="stay",
        revealed_secret=False,
        vocab_candidates=list(vocab_candidates),
    )


def out_of_scope_turn(session: Session):
    return session.settle(
        in_scope=False,
        severity="none",
        used_target_language=False,
        target_words=0,
        quest_signal="stay",
        revealed_secret=False,
        vocab_candidates=[],
    )


# ---------------------------------------------------------------- 命中判定
class TestMatchTargetVocab:
    def test_en_hits_return_in_vocab_order(self):
        # 按词表序而不是出现序：前端进度条按词表画，顺序要稳定
        assert match_target_vocab("Please, one miso ramen!", VOCAB, "space") == ["ramen", "please"]

    def test_en_case_insensitive_and_deduped(self):
        assert match_target_vocab("RAMEN Ramen ramen", VOCAB, "space") == ["ramen"]

    def test_en_plural_tolerance(self):
        assert match_target_vocab("Two bowls arrived.", VOCAB, "space") == ["bowl"]

    def test_en_no_arbitrary_prefix_match(self):
        # 只容忍 s/es 复数，"seated" 不算命中 "seat"
        assert match_target_vocab("I was seated.", VOCAB, "space") == []

    def test_ja_substring_match(self):
        vocab = ["ラーメン", "ください"]
        assert match_target_vocab("ラーメンをください", vocab, "char") == ["ラーメン", "ください"]


# ---------------------------------------------------------------- 能量账本
class TestEnergyEconomy:
    def test_baseline_no_vocab_drains_on_turn_17(self):
        # 100 / 6 = 16.67 → 第 17 轮耗尽。不吃词的玩家体验与改动前完全一致。
        s = Session(scene=make_scene())
        for _ in range(16):
            assert clean_turn(s).status == "playing"
        assert clean_turn(s).status == "drained"
        assert s.turn_count == 17

    def test_new_vocab_hit_refunds_energy(self):
        s = Session(scene=make_scene())
        clean_turn(s)  # 先离开满能量，避免上限截断干扰断言
        before = s.energy
        out = clean_turn(s, ["ramen"])
        assert out.vocab_new_hits == ["ramen"]
        assert out.energy_delta == -Rules.energy_per_turn + Rules.energy_per_vocab_hit
        assert out.energy_refund == Rules.energy_per_vocab_hit
        assert s.energy == before + out.energy_delta

    def test_same_word_not_rewarded_twice(self):
        s = Session(scene=make_scene())
        clean_turn(s, ["ramen"])
        out = clean_turn(s, ["ramen"])
        assert out.vocab_new_hits == []
        assert out.energy_delta == -Rules.energy_per_turn

    def test_per_turn_cap_leaves_extra_words_collectable(self):
        s = Session(scene=make_scene())
        clean_turn(s)
        out = clean_turn(s, ["ramen", "bowl", "soup", "broth"])
        assert out.vocab_new_hits == ["ramen", "bowl", "soup"]
        # 超出单轮上限的词没有被烧掉：下一轮再说仍然有奖励
        assert clean_turn(s, ["broth"]).vocab_new_hits == ["broth"]

    def test_energy_capped_at_start_and_delta_not_overreported(self):
        s = Session(scene=make_scene())
        out = clean_turn(s, ["ramen", "bowl", "soup"])  # 100 - 6 + 9 → 封顶 100
        assert s.energy == Rules.energy_start
        assert out.energy_delta == 0  # 实际生效值，被上限截掉的部分不虚报
        assert out.energy_refund == Rules.energy_per_turn  # 有效返还 6：9 里有 3 被上限吃掉

    def test_no_refund_when_out_of_scope(self):
        s = Session(scene=make_scene())
        out = s.settle(
            in_scope=False, severity="none", used_target_language=True,
            target_words=0, quest_signal="stay", revealed_secret=False,
            vocab_candidates=["ramen"],
        )
        assert out.vocab_new_hits == []

    def test_no_refund_without_target_language(self):
        s = Session(scene=make_scene())
        out = s.settle(
            in_scope=True, severity="major", used_target_language=False,
            target_words=0, quest_signal="stay", revealed_secret=False,
            vocab_candidates=["ramen"],
        )
        assert out.vocab_new_hits == []

    def test_full_collection_extends_run_to_turn_22(self):
        # 贪婪满命中（前 5 轮吃完 14 词）：满能量时上限截断浪费 4×3=12，
        # (100 + 42 - 12) / 6 = 21.67 → 第 22 轮耗尽。落在 22-25 的目标区间；
        # 会省着用的玩家上限 (100+42)/6 = 23.67 → 24 轮。
        s = Session(scene=make_scene())
        remaining = list(VOCAB)
        turn = 0
        out = None
        while s.status == "playing":
            turn += 1
            batch, remaining = remaining[:3], remaining[3:]
            out = clean_turn(s, batch)
        assert out is not None and out.status == "drained"
        assert turn == 22

    def test_state_and_summary_expose_vocab_metrics(self):
        s = Session(scene=make_scene())
        clean_turn(s, ["ramen", "bowl"])
        state = s.public_state()
        assert state["vocab_hit_count"] == 2
        assert state["vocab_total"] == len(VOCAB)
        summary = s.summary()
        assert summary["vocab_hits"] == 2
        # 满能量时 -6+6 正好持平：有效返还 6（相对"没吃词"的路径多出来的量）
        assert summary["energy_regained"] == 6


# ---------------------------------------------------------------- 出戏计数
class TestStrikes:
    def test_three_consecutive_strikes_crash(self):
        s = Session(scene=make_scene())
        out_of_scope_turn(s)
        out_of_scope_turn(s)
        assert out_of_scope_turn(s).status == "crashed"

    def test_in_scope_turn_resets_strikes(self):
        # 文案承诺的是「连续 3 次」（intro.js），实现要匹配文案
        s = Session(scene=make_scene())
        out_of_scope_turn(s)
        out_of_scope_turn(s)
        clean_turn(s)  # 说回正题
        out = out_of_scope_turn(s)
        assert s.strikes == 1
        assert out.status == "playing"

    def test_alternating_grief_still_crashes_by_suspicion(self):
        # strikes 重置不等于可以无限骚扰：出戏 +20 / 回稳 -5，净 +15/对，suspicion 会兜住
        s = Session(scene=make_scene())
        for _ in range(10):
            if s.status != "playing":
                break
            out_of_scope_turn(s)
            if s.status != "playing":
                break
            clean_turn(s)
        assert s.status == "crashed"
