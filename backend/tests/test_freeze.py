"""数值冻结自检。

内测开始后，Rules 的数值与 severity 映射表都不能再动 —— 中途改会毁掉
A/B 与留存数据的可比性（前后两批玩家玩的不是同一个游戏，指标却混在一张表里）。
这是一条产品纪律，不是代码约束，所以要有一个测试把它变成会响的东西。

快照刻意硬编码字面值。写成 `assert Rules.energy_start == Rules.energy_start`
式的"动态自检"是永远绿的假检 —— 它只能证明代码能运行，证明不了数值没被改。

要真的改数值：先决定撤销冻结（并说明为什么值得放弃已收集数据的可比性），
再改这里的快照，最后改 config。顺序反了就说明纪律已经失效了。
"""

from config import IGNORED_ERROR_TYPES, SEVERITY_BY_TYPE, Rules

FROZEN_RULES = {
    "suspicion_start": 30,
    "suspicion_max": 100,
    "suspicion_floor": 12,
    "min_turns_per_stage": 2,
    "d_out_of_scope": 20,
    "d_error_major": 14,
    "d_error_minor": 6,
    "d_clean": -5,
    "d_stage_advance": -6,
    "energy_start": 100,
    "energy_per_turn": 6,
    "energy_per_vocab_hit": 3,
    "vocab_hits_per_turn_cap": 3,
    "strikes_to_crash": 3,
    "glitch_bands": [(40, 0), (60, 1), (80, 2), (101, 3)],
}

FROZEN_SEVERITY = {
    "be_mismatch": "major",
    "aux_missing": "major",
    "negation_form": "major",
    "verb_form": "major",
    "agreement": "major",
    "non_target_language": "major",
    "copula_omission": "minor",
    "tense_marker": "minor",
    "article": "minor",
    "countability": "minor",
    "plural_form": "minor",
    "word_order": "minor",
    "preposition": "minor",
    "collocation": "minor",
    "quantifier": "minor",
    "register": "minor",
}

FROZEN_IGNORED = {"contraction", "synonym", "formality", "punctuation",
                  "capitalization", "possessive"}

_WHY = ("数值已冻结（内测期）。改它意味着放弃前后两批玩家数据的可比性 —— "
        "如果确实要改，先在 README/evidence 里写下为什么，再更新本文件的快照。")


def test_rules_are_frozen():
    actual = {name: getattr(Rules, name) for name in FROZEN_RULES}
    assert actual == FROZEN_RULES, _WHY


def test_severity_mapping_is_frozen():
    assert SEVERITY_BY_TYPE == FROZEN_SEVERITY, _WHY


def test_ignored_types_are_frozen():
    assert set(IGNORED_ERROR_TYPES) == FROZEN_IGNORED, _WHY


def test_severity_table_covers_every_type_exactly_once():
    """两张表不能有交集：一个 type 要么判档位，要么整条丢弃，不能既是又不是。"""
    assert not (set(SEVERITY_BY_TYPE) & set(IGNORED_ERROR_TYPES))
