"""人设维锚点样本的结构自检。

这套样本要回答的问题是：**裁判的 persona_consistency 维会不会扣分？**
evidence-07 §7 记着一条可疑之处 —— 五套 live trace 的人设分全是 5.00。
要么 Persona 真的稳，要么这一维根本不会扣分，而后者意味着这个指标一直在自欺。

所以这里最要紧的一条测试是 `test_scorer_fails_an_all_five_judge`：
如果打分器对「全给 5 分」的裁判也判通过，那它就证伪不了任何东西，
整套样本白写。工具必须先有能力判我怀疑的那件事有罪。
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))

import anchors  # noqa: E402
import judge  # noqa: E402


def _judgment(trace: dict, scores) -> dict:
    """伪造一份裁判结果。scores 可以是常数，也可以是逐轮列表。"""
    if isinstance(scores, int):
        scores = [scores] * len(trace["turns"])
    return {
        "judge_mode": "model",
        "turns": [
            {"index": i, "persona_consistency": s, "pedagogy_compliance": 5,
             "safety": 5, "reason": ""}
            for i, s in enumerate(scores, 1)
        ],
    }


# ------------------------------------------------------------ 打分器的有效性

def test_scorer_fails_an_all_five_judge():
    """全给 5 分的裁判必须挂在 hard 行上 —— 这是整套样本存在的理由。"""
    trace = anchors.build_traces(splits=["dev"])[0]
    result = anchors.score(trace, _judgment(trace, 5))

    assert result["hard"]["total"] > 0, "dev 套里没有 hard 样本，测不出宽松"
    assert result["hard"]["hit"] == 0, "hard 样本被判 5 分却算命中，打分器无效"
    assert not result["passed"]


def test_scorer_passes_a_judge_that_scores_every_anchor_in_band():
    trace = anchors.build_traces(splits=["dev"])[0]
    ideal = [anchors.BANDS[t["anchor"]["kind"]][0] for t in trace["turns"]]
    result = anchors.score(trace, _judgment(trace, ideal))

    assert result["passed"]
    assert result["hard"]["hit"] == result["hard"]["total"]
    assert result["clean"]["hit"] == result["clean"]["total"]


def test_scorer_flags_false_alarms_on_clean_turns():
    """把好好说话的一轮判成 1 分同样是坏事 —— 不能只罚漏报不罚误报。"""
    trace = anchors.build_traces(splits=["dev"])[0]
    result = anchors.score(trace, _judgment(trace, 1))

    assert result["clean"]["hit"] == 0
    assert not result["passed"]


# ------------------------------------------------------------ 样本本身的纪律

def test_bands_follow_the_rubric_and_do_not_overlap():
    assert anchors.BANDS["clean"] == (4, 5)
    assert anchors.BANDS["hard"] == (1, 2)
    lo_clean, _ = anchors.BANDS["clean"]
    _, hi_hard = anchors.BANDS["hard"]
    assert hi_hard < lo_clean, "hard 与 clean 的分带重叠，命中就失去了意义"


def test_every_anchor_declares_kind_and_reason():
    for row in anchors.ANCHORS:
        assert row["kind"] in anchors.BANDS, row
        assert row["split"] in ("dev", "holdout"), row
        assert row["why"].strip(), f"{row['npc'][:30]} 没写为什么该扣分"


def test_each_trace_is_mostly_clean_so_a_break_stands_alone():
    """真实 trace 是一整片好回复里混着个别坏的。
    锚点样本要是坏的占多数，裁判可以靠批内对比取巧，量出来的宽严不作数。"""
    for trace in anchors.build_traces():
        kinds = [t["anchor"]["kind"] for t in trace["turns"]]
        assert kinds.count("clean") > len(kinds) - kinds.count("clean"), trace["scene_id"]
        assert len(kinds) <= judge.JUDGE_BATCH, "一条锚点 trace 不该跨批"


def test_dev_and_holdout_share_no_npc_line():
    dev = {r["npc"] for r in anchors.ANCHORS if r["split"] == "dev"}
    holdout = {r["npc"] for r in anchors.ANCHORS if r["split"] == "holdout"}
    assert dev and holdout
    assert not (dev & holdout)


def test_holdout_covers_a_second_scene():
    """只在拉面馆上调好的 rubric，不算调好。"""
    scenes = {r["scene_id"] for r in anchors.ANCHORS if r["split"] == "holdout"}
    assert len(scenes) >= 2


def test_every_hard_kind_is_a_distinct_failure_mode():
    modes = [r["mode"] for r in anchors.ANCHORS if r["kind"] == "hard"]
    assert len(modes) >= 5
    assert len(set(modes)) >= 5, "hard 样本的出戏方式重复了，覆盖面没有看上去那么宽"


# ------------------------------------------------------------ 与裁判管线对接

def test_built_traces_survive_the_real_judge_prompt_path():
    """锚点必须走与真 trace 完全相同的代码路径，否则标定不迁移。"""
    for trace in anchors.build_traces():
        block = "\n".join(judge._turn_block(i, t) for i, t in enumerate(trace["turns"], 1))
        for t in trace["turns"]:
            assert t["npc_text"] in block

        scored = judge.judge_heuristically(trace)
        assert len(scored["turns"]) == len(trace["turns"])


def test_heuristic_judge_catches_the_self_outing_anchors():
    """离线兜底打分器至少要抓住自称 AI / 讲语法这两类正则可见的出戏。"""
    for trace in anchors.build_traces():
        scored = judge.judge_heuristically(trace)
        for turn, row in zip(trace["turns"], scored["turns"]):
            if turn["anchor"]["mode"] in ("ai_self_disclosure", "grammar_lecture"):
                assert row["persona_consistency"] <= 2, turn["npc_text"]


@pytest.mark.parametrize("split", ["dev", "holdout"])
def test_split_filter_returns_only_that_split(split):
    for trace in anchors.build_traces(splits=[split]):
        assert {t["anchor"]["split"] for t in trace["turns"]} == {split}


# ------------------------------------------------------------ 标定报告的呈现

def _run_result(hard_scores):
    """造一份 dev 标定结果，hard 行的分由参数给定。"""
    import judge_anchors  # noqa: F401  确保模块存在
    trace = anchors.build_traces(splits=["dev"])[0]
    it = iter(hard_scores)
    scores = [next(it) if t["anchor"]["kind"] == "hard"
              else anchors.BANDS[t["anchor"]["kind"]][0] for t in trace["turns"]]
    return anchors.score(trace, _judgment(trace, scores))


def test_report_headlines_the_verdict():
    import judge_anchors

    lenient = judge_anchors.render_report([_run_result([5, 5, 5])])
    strict = judge_anchors.render_report([_run_result([1, 1, 2])])

    assert "不会扣分" in lenient
    assert "不会扣分" not in strict


def test_report_names_every_hard_anchor_the_judge_let_through():
    import judge_anchors

    text = judge_anchors.render_report([_run_result([5, 1, 5])])

    slipped = [r for r in _run_result([5, 1, 5])["rows"]
               if r["kind"] == "hard" and not r["hit"]]
    assert len(slipped) == 2
    for row in slipped:
        assert row["mode"] in text
        assert row["npc_text"][:40] in text
