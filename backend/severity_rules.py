"""语病档位的代码规则（rubric v2-typed）。

v1 的档位由 LLM 在散文 rubric + few-shot 下直出，boundary 留出集上
同配置重跑波动 10 个百分点，且解释不了错在哪。v2 把分工改成：
模型只做「抽取」（span / fix / type / note），档位由 config.SEVERITY_BY_TYPE
的映射决定。错了能一眼分清：是抽取错（span/type 不对）还是映射错（表定错了档）。

规则放 backend/ 而不是 eval/：agents.assess() 是线上和评测的同一条路径，
口径放这里两边自动一致，不会出现"评测通过但线上不一样"。
"""

from __future__ import annotations

import re

from config import IGNORED_ERROR_TYPES, SEVERITY_BY_TYPE

# 档位判定逻辑的版本号。写进评测 trace —— 不同 rubric 下的分数不可比，
# 报告必须能说清一份 trace 是按哪套口径打的。
RUBRIC_VERSION = "v2-typed"

_RANK = {"none": 0, "minor": 1, "major": 2}

_STRIP = re.compile(r"[\W_]+", re.UNICODE)


def _normalize(text: str) -> str:
    """比较 span/fix 是否实质相同：去掉标点/空白/大小写差异。不排序 —— 语序修正不能误杀。"""
    return _STRIP.sub("", text.casefold())


def filter_errors(errors: list[dict]) -> list[dict]:
    """丢掉不该存在的"错误"：白名单 type，以及 fix 与 span 实质相同的挑刺。

    后者是给模型漏标 type 时的代码兜底 —— 标点/大小写/撇号级别的"修正"
    归一化后和原文一样，无论它自称什么 type 都不是错误。
    """
    kept = []
    for error in errors:
        if str(error.get("type", "")) in IGNORED_ERROR_TYPES:
            continue
        fix = str(error.get("fix", ""))
        if fix and _normalize(fix) == _normalize(str(error.get("span", ""))):
            continue
        kept.append(error)
    return kept


def classify(errors: list[dict], used_target_language: bool) -> tuple[str, list[str]]:
    """由错误类型算档位。返回 (severity, 未知type列表)。

    未知 type 按 minor 计但必须回传 —— 可见降级：静默错档在评测里
    表现为"分数变了但没人知道为什么"，和静默降级到规则桩是同一种病。
    """
    if not used_target_language:
        return "major", []

    severity = "none"
    unknown: list[str] = []
    for error in errors:
        type_ = str(error.get("type", ""))
        mapped = SEVERITY_BY_TYPE.get(type_)
        if mapped is None:
            unknown.append(type_)
            mapped = "minor"
        if _RANK[mapped] > _RANK[severity]:
            severity = mapped
    return severity, unknown
