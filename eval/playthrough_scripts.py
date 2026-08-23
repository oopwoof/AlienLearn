"""整局评测用的玩家台词脚本。

一场景一份，按四幕的推进节奏写：寒暄 → 正事 → 建立联结 → 追问秘密。
台词刻意写成"一个语言还行但不完美的学习者"会说的话，不是完美英语 ——
整局评测量的是"正常玩家能不能通关"，不是"完美输入下管线能不能跑"。

放在 eval/ 而不是场景 JSON 里：JSON 会被拼进 Agent 的 system prompt，
台词进了 prompt 就等于把答案给了模型（check_leakage 拦的就是这件事）。

尾部的 FILLER 是安全垫：如果 NPC 比预期难松口，脚本不至于提前用完台词，
"台词耗尽仍在进行中"会被记成 stalled 而不是伪装成通关失败。
"""

from __future__ import annotations

FILLER = [
    "Please, tell me a little more.",
    "I understand. Thank you for telling me.",
    "That is very kind of you.",
]

SCRIPTS: dict[str, list[str]] = {
    "ramen_en": [
        "Good evening. Do you have a seat for one?",
        "It is raining hard tonight. I am very hungry.",
        "One miso ramen, please. Is the soup hot?",
        "This is delicious. The broth tastes different from other shops.",
        "You have worked here many years? The shop feels old and warm.",
        "What makes your broth so special? Is it a secret recipe?",
        "I am asking because I want to remember this taste. Please tell me.",
        "Thank you. Your secret is safe with me tonight.",
    ],
    "ramen_ja": [
        "こんばんは。すみません、一人ですが席ありますか。",
        "今夜は雨ですね。お腹すいた。",
        "ラーメンを一杯お願いします。みそでお願いします。",
        "スープが熱くておいしいです。他の店と違いますね。",
        "ここは長いですか。お店が古くて、いい感じです。",
        "この出汁の秘密は何ですか。レシピを教えてくれますか。",
        "この味を覚えたいんです。お願いします。",
        "ありがとう。秘密は誰にも言いません。",
    ],
    "flower_en": [
        "Good evening! Are you still open? I need flowers.",
        "A gift for my mother, it is her birthday tomorrow.",
        "She loves pink roses. Can you wrap some fresh ones?",
        "They smell beautiful. How do you keep them so fresh?",
        "You have been here a long time? This street feels like it has stories.",
        "Those white flowers in the window are lovely. Camellias, right?",
        "Who orders the white camellias every Wednesday? They never leave a name?",
        "I am sorry for asking. But it sounds like a beautiful story. Please tell me.",
        "Thank you. I will keep it to myself.",
    ],
}


def script_for(scene_id: str) -> list[str]:
    """取台词。没写过的场景退回一段通用脚本 —— 新场景先能跑，再谈调参。"""
    lines = SCRIPTS.get(scene_id)
    if lines is None:
        lines = [
            "Good evening. Sorry, are you still open?",
            "I am just looking around. This place is nice.",
            "How long have you worked here?",
            "You must know this place better than anyone.",
            "Can I ask you something? I am curious about this place.",
            "It sounds like there is a story here. Please tell me.",
        ]
    return [*lines, *FILLER]
