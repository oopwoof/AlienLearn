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

# 安全垫写成"还在追问"而不是"客套告辞"：告辞会让 NPC 顺势收尾，
# 于是脚本长度反而变成通关的隐性上限，量出来的就不是任务本身的难度了。
FILLER = [
    "Please, tell me a little more.",
    "I am really asking. What is the story there?",
    "I will not tell anyone. Please.",
    "It matters to me. Who was it?",
    "Thank you. I understand now.",
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
    "flower_ja": [
        "こんばんは。すみません、まだ開いてますか。花がほしいです。",
        "母に贈り物です。明日は誕生日なんです。",
        "ピンクのバラが好きです。新しいのを包んでくれますか。",
        "いい匂いですね。水はどのくらいあげますか。",
        "この店は長いですか。この通り、朝はきれいでしょうね。",
        "窓のあの白い椿、きれいですね。",
        "毎週水曜日、あれは誰が頼むんですか。名前を書かないんですか。",
        "ごめんなさい、聞きすぎました。でも、いい話みたいだから。教えてください。",
        "ありがとう。誰にも言いません。",
    ],
    "bookshop_en": [
        "Good evening. Sorry, are you still open? I am looking for a book.",
        "I cannot sleep tonight. I want something quiet to read.",
        "Something old is fine. Not a new story, an old one.",
        "This page smells like dust. I like that. Do you read them all?",
        "You have been here many years? The canal outside is very quiet now.",
        "That book behind the counter has no price. What is it?",
        "Who is the author? The title is not on the cover.",
        "I am sorry to ask. But I would like to remember it. Please tell me.",
        "Thank you. I will not tell anyone.",
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
