"""severity 档位代码规则（rubric v2-typed）的口径测试。

v1 的档位由 LLM 直出，boundary 集上同配置重跑波动 10 个百分点还解释不了。
v2 的分工：模型只抽取（span/fix/type），档位由映射表决定 ——
错了能一眼分清是抽取错还是映射错。这里钉死映射口径。
"""

from severity_rules import RUBRIC_VERSION, classify, filter_errors


def err(type_: str, span: str = "he have", fix: str = "he has") -> dict:
    return {"span": span, "fix": fix, "type": type_, "note": "测试"}


class TestClassify:
    def test_skeleton_type_maps_to_major(self):
        assert classify([err("be_mismatch")], True) == ("major", [])

    def test_surface_type_maps_to_minor(self):
        assert classify([err("article")], True) == ("minor", [])

    def test_copula_omission_is_minor_but_mismatch_is_major(self):
        # 省略 be（This soup very good）是口音式零系动词 —— 母语者照常接话；
        # 用错 be（I is）才是骨架错。两者不能共用一个档
        assert classify([err("copula_omission")], True) == ("minor", [])
        assert classify([err("be_mismatch")], True) == ("major", [])

    def test_no_errors_is_none(self):
        assert classify([], True) == ("none", [])

    def test_highest_tier_wins(self):
        errors = [err("tense_marker"), err("aux_missing"), err("article")]
        assert classify(errors, True) == ("major", [])

    def test_unknown_type_falls_to_minor_and_stays_visible(self):
        # 可见降级：未知 type 不能静默错档，要能在埋点/评测里看到
        severity, unknown = classify([err("weird_new_type")], True)
        assert severity == "minor"
        assert unknown == ["weird_new_type"]

    def test_non_target_language_forces_major(self):
        # 现有代码规则的延续：整句没用目标语言，无论模型报什么都是 major
        assert classify([], False) == ("major", [])


class TestFilterErrors:
    def test_whitelisted_type_is_dropped(self):
        # 缩略/近义/正式度/标点/大小写/所有格：一律不是错误
        assert filter_errors([err("contraction"), err("formality")]) == []

    def test_punctuation_only_fix_is_dropped(self):
        # 兜底：模型漏标 type 时，「fix 归一化后和 span 相同」的挑刺也要拦住
        nag = {"span": "dont", "fix": "don't", "type": "verb_form", "note": ""}
        assert filter_errors([nag]) == []

    def test_case_only_fix_is_dropped(self):
        nag = {"span": "i am tired", "fix": "I am tired", "type": "agreement", "note": ""}
        assert filter_errors([nag]) == []

    def test_real_error_kept_including_word_order(self):
        # 语序错误的 fix 是同一批词换序 —— 归一化不排序，不能误杀
        reorder = {"span": "hungry very", "fix": "very hungry", "type": "word_order", "note": ""}
        kept = filter_errors([err("be_mismatch", "I is", "I am"), reorder])
        assert len(kept) == 2


def test_rubric_version_is_stamped():
    assert RUBRIC_VERSION == "v2-typed"
