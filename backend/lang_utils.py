"""语言检测与"主动目标语言输出量"计数 —— 北极星指标的底层度量。"""

from __future__ import annotations

import re

_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
_KANA = re.compile("[぀-ゟ゠-ヿ]")
_CJK = re.compile("[一-鿿]")


def count_target_words(text: str, mode: str) -> int:
    """英语按词计，日语等按有效字符计（去掉标点和空白）。"""
    if mode == "space":
        return len(_LATIN_WORD.findall(text))
    return len(_KANA.findall(text)) + len(_CJK.findall(text))


def looks_like_target_language(text: str, language_code: str) -> bool:
    """粗判是否在用目标语言。够用就好 —— live 模式下模型会给出更准的判断。"""
    stripped = text.strip()
    if not stripped:
        return False

    latin = len(_LATIN_WORD.findall(stripped))
    kana = len(_KANA.findall(stripped))
    cjk = len(_CJK.findall(stripped))

    if language_code == "en":
        # 出现汉字/假名且拉丁词很少 —— 玩家在用母语说话
        return latin >= 1 and (cjk + kana) <= max(0, latin // 4)
    if language_code == "ja":
        # 日语必须有假名（纯汉字可能只是中文）
        return kana >= 1
    return latin >= 1
