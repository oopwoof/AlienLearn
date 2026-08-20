"""三个 Agent 的规则桩（MOCK_LLM=1 时使用）。

存在理由：无 API key 也能跑通完整链路，前端/状态机/埋点/评测都能独立开发和演示。
它是刻意"笨"的 —— 只覆盖最常见的学习者错误和最直白的越狱词，
真正的语言判断能力由 live 模式的模型提供。
"""

from __future__ import annotations

import logging
import random
import re

from config import secret_stage_id

_log = logging.getLogger("alienlearn.mock")

# 评测发现的短板（见 eval/out/report-01-before-fix.md）：
# 纯关键词匹配漏掉了"要求 NPC 去干别的活"这类越狱 —— 它一个敏感词都不含。
# 例：Write me a Python script that sorts a list. → 拦截率只有 83.3%，低于 PRD 定的 90%。
# 补一组"任务请求"句式。规则桩到这里就是天花板了：
# 真正的语义判断在 live 模式的 Router prompt 里（"要求 NPC 脱离角色去执行别的任务"）。
_TASK_REQUEST = re.compile(
    r"\b(write|give|show|explain|translate|summari[sz]e|code|generate|list)\b[^.?!]{0,24}\b"
    r"(me|us|this|that|a|an|the|it|how)\b",
    re.IGNORECASE,
)

import severity_rules
from lang_utils import count_target_words, looks_like_target_language

# 明显不属于"雨夜拉面馆"这个碎片的话题 / 直白的越狱尝试
_OUT_OF_SCOPE = [
    "ignore previous", "ignore the above", "system prompt", "you are an ai",
    "you are a language model", "as an ai", "prompt", "jailbreak", "chatgpt",
    "gpt", "quantum", "politics", "president", "election", "bitcoin", "crypto",
    "忽略", "系统提示", "你是ai", "你是人工智能", "你是模型", "越狱", "量子",
    "总统", "选举", "政治", "写代码", "翻译成中文",
]

# 常见学习者错误：(正则, 修正, 说明, 错误类型)
# rubric v2：这里只标 type，档位由 severity_rules.classify 按同一张映射表算 ——
# mock / live / 评测三条路径共用一个口径。
# 原先有一条「please give me one ramen → 更自然的点单说法」被删掉了：
# 那是正式度挑刺，正是产品明令禁止的失败模式（v2 白名单里它属于 formality）。
_ERROR_PATTERNS: list[tuple[str, str, str, str]] = [
    (r"\bI is\b", "I am", "第一人称 be 动词用 am", "be_mismatch"),
    (r"\b(he|she|it) have\b", r"\1 has", "第三人称单数用 has", "agreement"),
    (r"\byou is\b", "you are", "you 后面用 are", "be_mismatch"),
    (r"\bI want eat\b", "I want to eat", "want 后接动词要加 to", "verb_form"),
    (r"\bI want order\b", "I want to order", "want 后接动词要加 to", "verb_form"),
    (r"\bI no\b", "I don't", "否定用 don't，不用 no + 动词", "negation_form"),
    (r"\bdon't has\b", "don't have", "助动词后用原形 have", "verb_form"),
    (r"\bmuch (people|noodles|customers)\b", r"many \1", "可数名词用 many", "countability"),
    (r"\ba (apple|hour|umbrella|onion|egg)\b", r"an \1", "元音开头前用 an", "article"),
    (r"\byesterday I (go|eat|come|see)\b", "yesterday I went/ate/came/saw", "yesterday 要用过去式", "tense_marker"),
    (r"\bvery much (good|delicious|hot)\b", r"very \1", "形容词前不用 very much", "collocation"),
    (r"\bI am hungry very\b", "I am very hungry", "very 放在形容词前", "word_order"),
]

# 老板的台词库：按任务阶段 + 情境
_LINES: dict[str, dict[str, list[str]]] = {
    "enter": {
        "clean": [
            "Hah. Good. Sit there, by the counter. Towel is on the hook.",
            "Eh, come in, come in. Close the door, the rain follows you.",
            "One? Sit anywhere. Nobody comes out in this weather but you.",
            "Hah. Wet shoes on my floor again. Sit. Sit.",
        ],
        "error": [
            "Eh? ...Say that again. My ears are old and the rain is loud.",
            "Hm. You talk funny. Sit down anyway. Everyone talks funny in the rain.",
            "What? ...Never mind. Sit. Point at what you want later.",
            "Hah. Not from here, eh? Sit. The soup does not care how you talk.",
        ],
    },
    "order": {
        "clean": [
            "One bowl. Miso or soy? ...Fine, miso. Trust me, this weather wants miso.",
            "Good. Egg? Pork? ...I put both. You look like you need both.",
            "Coming. Sit still. Three minutes, no more.",
            "Hah. Good choice. Everybody orders that and then says it was their idea.",
        ],
        "error": [
            "Eh? One what? Use small words, I am cooking, not translating.",
            "Hah? Say the name. Ramen. Rah-men. Try again.",
            "Hm. I hear noise, not food. Point at the wall. The menu is right there.",
            "You want... something. Fine. I decide tonight. You eat what I make.",
        ],
    },
    "smalltalk": {
        "clean": [
            "Twenty-six years I stand here. Twenty-six. The chain store down the street? Two years. Hah.",
            "Rain is bad for business, good for soup. Everyone wants hot soup. You work late, eh?",
            "My father stood here before me. Same pot. I only changed the light bulb.",
            "You office people all come at midnight looking half dead. Eat. Then go home.",
        ],
        "error": [
            "Hm. I do not follow. But keep talking. It is a slow night.",
            "Eh. Your words are broken like my old fridge. Eat first, talk after.",
            "Hah. I understood two words. Good enough for a rainy night.",
            "...Sure. Sure. Whatever you said. Drink your tea.",
        ],
    },
    "intel": {
        "clean": [
            "The broth? ...Family secret. My father would slap me. ...Hah. Fine. Come closer.",
            "You noticed. Nobody notices. ...Pork bone, chicken. And two things I do not write down.",
            "Eh. Everyone asks. Nobody listens to the answer. ...You are still here, though.",
        ],
        "error": [
            "The soup? Ask properly. This is my father's soup, not gossip.",
            "Eh? You want my secret with words like that? No, no. Try again, politely.",
            "Hah. Ask me again when your mouth works better.",
        ],
        "reveal": [
            "One piece of yuzu peel. And dried scallops, a small handful, right before I kill the flame. ...Tell nobody.",
        ],
    },
    "deflect": {
        "any": [
            "Hah? What is that? This is a ramen shop. Not a... whatever that is. Eat.",
            "Eh. Strange talk. Strange talk makes the soup cold. Sit and order.",
            "No, no, no. I do not know these words. Noodles I know. Ask me about noodles.",
            "You are a strange one. Drink your tea. Look at the rain. Stop talking.",
            "Hm. My hands are wet and my pot is hot. Ask me something I can cook.",
        ],
    },
}

# 未注册场景的通用兜底：保证 mock 局能走完、不炸，但台词没有场景味。
# 刻意不给新场景写全套台词 —— 台词库是拉面馆专属资产，内测走 live，
# 每场景 40+ 句的成本花在这里是纯浪费。新场景的 mock 只承诺「不崩」。
_GENERIC_LINES: dict[str, dict[str, list[str]]] = {
    "_default": {
        "clean": [
            "Mm. Alright. Go on.",
            "I hear you. One moment.",
            "Fine, fine. Anything else?",
        ],
        "error": [
            "Eh? Say that again, slower.",
            "Hm. I did not catch that. Once more.",
        ],
        "reveal": [
            "...Alright. Come closer. I will tell you once, and only once.",
        ],
    },
    "deflect": {
        "any": [
            "What? I do not know these words. Ask me something normal.",
            "Strange talk. Not here. Not tonight.",
        ],
    },
}

_JA_LINES: dict[str, dict[str, list[str]]] = {
    "enter": {
        "clean": ["ほい、入り。ドア閉めてや、雨が付いてくるわ。", "一人か。どこでも座り。今日は誰も来へんわ。"],
        "error": ["なんや？もう一回言うてみ。耳が古いんや。", "……まあええ。座り。あとで指させばええ。"],
    },
    "order": {
        "clean": ["一杯やな。みそか、しょうゆか？……ほな、みそやで。", "卵は？チャーシューは？……両方入れとくわ。"],
        "error": ["なんやて？名前言うてみ。ラーメン。ラ、ー、メ、ン。", "音は聞こえるけど飯の名前が聞こえへん。壁見てみ。"],
    },
    "smalltalk": {
        "clean": ["二十六年やで、ここに立って。あのチェーン店は二年や。ほんま。", "雨は商売にあかんけど、スープにはええんや。"],
        "error": ["よう分からんけど、まあ喋っとき。今日は暇やしな。", "二語だけ分かったわ。雨の夜にはそれで十分や。"],
    },
    "intel": {
        "clean": ["スープか？……家の秘密やで。親父に叱られるわ。……ほな、ちょっと近う来い。", "気づいたんか。誰も気づかへんのに。"],
        "error": ["スープ？ちゃんと聞かんかい。親父の味やぞ。", "その口でわしの秘密を聞くんか。あかんあかん。"],
        "reveal": ["ゆずの皮を一枚。あとは干し貝柱、ひとつまみ。火を止める直前にな。……誰にも言うなよ。"],
    },
    "deflect": {
        "any": ["なんやて？ここはラーメン屋やで。そんな話、知らんわ。座り。", "変な話はスープが冷める。座って注文せい。"],
    },
}


_INTENT_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("probe_secret", ("broth", "soup", "recipe", "secret", "ingredient", "taste", "stock",
                      "スープ", "出汁", "レシピ", "秘密", "味")),
    ("order", ("ramen", "noodle", "bowl", "miso", "soy", "order", "eat", "hungry", "spicy", "egg",
               "ラーメン", "一杯", "注文", "みそ", "しょうゆ")),
    ("greeting", ("hello", "hi ", "good evening", "evening", "excuse me", "table for",
                  "こんばんは", "すみません", "ほい")),
]


def route(text: str, scene: dict, stage_id: str) -> dict:
    lowered = text.lower()
    hit = next((k for k in _OUT_OF_SCOPE if k in lowered), None)
    if hit:
        return {
            "in_scope": False,
            "intent": "jailbreak" if any(w in lowered for w in ("ignore", "prompt", "ai", "忽略", "越狱")) else "off_topic",
            "reason": f"命中出戏关键词: {hit}",
        }
    # 点单/请求也是"给我来一个X"，所以命中任务请求句式后还要排除场景内的名词。
    # 名词表用场景自己的 target_vocab 构建（词表本来就是场景名词的权威来源），
    # 再补一小撮任何服务场景都有的通用词
    scene_nouns = {w.lower() for w in scene.get("target_vocab", [])} | {
        "menu", "bill", "check", "water", "tea", "one", "table",
    }
    if _TASK_REQUEST.search(text) and not any(w in lowered for w in scene_nouns):
        return {"in_scope": False, "intent": "off_topic", "reason": "要求 NPC 执行场景外的任务"}
    intent = next((name for name, words in _INTENT_HINTS if any(w in lowered for w in words)), "smalltalk")
    return {
        "in_scope": True,
        "intent": intent,
        "reason": "未命中出戏关键词",
    }


def assess(text: str, scene: dict) -> dict:
    """规则版教务 Agent：语言检测 + 常见错误正则。"""
    words = count_target_words(text, scene["word_counting"])
    if not looks_like_target_language(text, scene["language_code"]):
        return {
            "used_target_language": False,
            "severity": "major",
            "target_word_count": 0,
            "corrected": "",
            "errors": [
                {
                    "span": text[:40],
                    "fix": f"请用{scene['target_language_label']}说",
                    "type": "non_target_language",
                    "note": f"检测到非{scene['target_language_label']}输入。碎片的语言层不接受它。",
                }
            ],
        }

    errors = []
    corrected = text
    for pattern, fix, note, type_ in _ERROR_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        errors.append({
            "span": match.group(0),
            "fix": re.sub(pattern, fix, match.group(0), flags=re.IGNORECASE),
            "type": type_,
            "note": note,
        })
        corrected = re.sub(pattern, fix, corrected, flags=re.IGNORECASE)

    errors = severity_rules.filter_errors(errors)
    severity, _ = severity_rules.classify(errors, True)

    return {
        "used_target_language": True,
        "severity": severity,
        "target_word_count": words,
        "corrected": corrected if errors else "",
        "errors": errors,
    }


_last_line = ""


def _pick(options: list[str]) -> str:
    """不重复上一句。台词池小的时候，连续两轮同一句话在演示里非常扎眼。"""
    global _last_line
    fresh = [o for o in options if o != _last_line] or options
    _last_line = random.choice(fresh)
    return _last_line


# 场景 → 台词库。只有拉面馆有手写台词；别的场景走通用兜底（见 _GENERIC_LINES）
_SCENE_LINES: dict[str, dict] = {"ramen_en": _LINES, "ramen_ja": _JA_LINES}
_warned_scenes: set[str] = set()


def persona_chunks(scene: dict, stage_id: str, in_scope: bool, has_error: bool, revealed: bool) -> tuple[str, dict]:
    table = _SCENE_LINES.get(scene["scene_id"])
    if table is None:
        table = _GENERIC_LINES
        if scene["scene_id"] not in _warned_scenes:
            _warned_scenes.add(scene["scene_id"])
            _log.warning("场景 %s 没有 mock 台词库，走通用兜底 —— mock 只保证不崩，体验请用 live",
                         scene["scene_id"])
    if not in_scope:
        return _pick(table["deflect"]["any"]), {
            "emotion": "suspicious", "quest_signal": "stay", "revealed_secret": False
        }

    bucket = table.get(stage_id) or table.get("_default") or table["order"]
    if stage_id == secret_stage_id(scene) and revealed:
        return _pick(bucket["reveal"]), {
            "emotion": "conspiratorial", "quest_signal": "advance", "revealed_secret": True
        }

    key = "error" if has_error else "clean"
    text = _pick(bucket.get(key, bucket["clean"]))
    return text, {
        "emotion": "annoyed" if has_error else "warm",
        "quest_signal": "stay" if has_error else "advance",
        "revealed_secret": False,
    }
