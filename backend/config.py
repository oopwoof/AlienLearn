"""集中读取环境变量与游戏数值，避免规则散落在各处。"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SCENES_DIR = Path(__file__).resolve().parent / "scenes"
FRONTEND_DIR = ROOT / "frontend"
DATA_DIR = ROOT / "data"

load_dotenv(ROOT / ".env")


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    mock_llm: bool = _flag("MOCK_LLM", "1")
    api_key: str = os.getenv("LLM_API_KEY", "").strip()
    base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").strip()
    model: str = os.getenv("LLM_MODEL", "deepseek-chat").strip()
    judge_model: str = os.getenv("JUDGE_MODEL", "").strip() or model
    default_scene: str = os.getenv("DEFAULT_SCENE", "ramen_en").strip()

    # 监听地址。做成可配置有两个实际原因：
    #   1. 本机 8000 常被别的项目占着，而占用时探活返回 404 而不是连接失败，极易误判
    #   2. 部署平台通常通过 PORT 注入端口，硬编码就没法上线
    host: str = os.getenv("HOST", "127.0.0.1").strip()
    port: int = int(os.getenv("PORT", "8000"))

    @property
    def live(self) -> bool:
        """真实调用模型的条件：没开 mock 且有 key。缺 key 时自动退回 mock，保证 demo 不会开天窗。"""
        return not self.mock_llm and bool(self.api_key)


SETTINGS = Settings()


# ---------------------------------------------------------------- 链路超时与重试
class Timeouts:
    """超时按「交互」和「批处理」分开设，因为两者对"慢"的容忍度差一个量级。

    为什么必须显式设：openai SDK 的默认值是 read=600s，等于没有超时。
    一次卡住的调用不会报错，它会让整轮对话冻住十分钟 —— 玩家看到的是
    老板把话说完、然后画面永久定格、输入框锁死。**这比直接报错难看得多。**

    交互路径实测单轮 1.4-4.0s（同一天内 DeepSeek 快慢差过一倍），12s 取的是
    「最慢观测值的 3 倍」。**不要为了 demo 手感把它调得更紧**：超时会退到本地规则桩，
    而规则桩的正则是照着 dev 集手写的 —— 它会让 dev 分数看起来正常但其实是假的。
    宁可多等两秒，也不要一个解释不了的满分。

    judge 是批处理，单次要生成 200×轮数+400 tokens，必须单独给宽松值，
    否则一改超时就把评测管线打死。
    """

    connect = 5.0              # 建连失败要快速失败 —— 网络抽风时重试比干等有用
    interactive_read = 12.0    # Router / Pedagogy / Persona
    judge_read = 180.0         # eval/judge.py 的批量打分
    max_retries = 2            # SDK 默认值。对"建连被拒"这类快速失败的抖动最有用

    # Agent 级硬上限：HTTP 层还在重试，也必须在这个时间内交出结果（可以是降级结果）。
    # 没有这一层，max_retries × read + backoff 会把最坏情况拖到 30s 以上。
    #
    # 为什么 14s 这个「不好看」的数字可以接受：卡住的位置在 orchestrator 里
    # NPC 说完话之后（await ped_task），玩家已经看到老板回话了，等的只是伪装度刷新。
    # 相比默认的 600s，这是 40 倍的改善；相比"更短的 deadline"，它不会伪造评测分数。
    agent_deadline = 14.0


# ---------------------------------------------------------------- 用量闸门
class Limits:
    """成本保险丝。内测阶段一个泄漏的链接就能把余额烧光，所以这层不能等公开发再加。

    日额度用完返回 503 拒绝（世界观内文案），**不降级到规则桩** ——
    内测是为了收真实数据，悄悄换规则桩会往数据集里灌垃圾局。
    频率限制返回 429，撞到它的通常不是真人。
    """

    # 今日真实模型调用轮数上限。0 = 不限。按 DeepSeek 的价格，几千轮也就几块钱，
    # 所以这个数是防"脚本失控"，不是防正常玩。
    daily_turn_budget = int(os.getenv("DAILY_TURN_BUDGET", "2000"))
    budget_refresh_sec = 20.0        # 额度计数的缓存窗口，避免每轮都查库

    turns_per_minute_per_player = int(os.getenv("TURNS_PER_MIN_PLAYER", "20"))
    turns_per_minute_per_ip = int(os.getenv("TURNS_PER_MIN_IP", "40"))


# ---------------------------------------------------------------- 游戏数值
class Rules:
    """所有可调数值集中一处 —— 调平衡时只改这里。"""

    # 起始 30，距离第一档 Glitch(40) 只有 10 点余量 —— 让玩家一开始就感到"薄冰上走路"
    suspicion_start = 30
    suspicion_max = 100
    # 伪装度有下限：你永远不是真的地球人，稳定度回不到满。清空张力等于清空玩法
    suspicion_floor = 12

    # 每个任务阶段的最少停留轮数。LLM 说"可以推进了"也得等 ——
    # 否则模型一放水，玩家四句寒暄就通关，"套话"这件事就没有戏了
    min_turns_per_stage = 2

    # 伪装度增减（正数 = 更可疑）。恢复慢、犯错快，是为了让"维持伪装"成为一件要用力的事。
    d_out_of_scope = 20        # 说了碎片里不该出现的话题（越狱/出戏）
    d_error_major = 14         # 严重语法错误，或压根没用目标语言
    d_error_minor = 6          # 轻微错误
    d_clean = -5               # 干净的一句话，伪装回稳
    d_stage_advance = -6       # 推进任务，老板放下戒心

    energy_start = 100
    energy_per_turn = 6        # ≈16 轮，正好一局 5-10 分钟

    # 词汇返能：把北极星（主动输出目标词）和生存（能量）绑在一起 ——
    # 「说目标语言」就是这个世界里的能量来源，主题自洽。
    # 账本：不吃词 17 轮不变；14 词全吃 +42 能量 ≈ 22-24 轮（满能量时的截断会吃掉一点）。
    # 只奖励"本局第一次用"的词（Session.vocab_used 去重），单轮封顶防词表沙拉；
    # 沙拉本身还会被 Pedagogy 判 major 罚伪装度，刷分行为自惩罚。
    energy_per_vocab_hit = 3
    vocab_hits_per_turn_cap = 3

    strikes_to_crash = 3       # 连续出戏次数上限，第三次触发硬崩溃（说回正题就重置）

    # 伪装度 → Glitch 档位（前端据此上特效）：0 平静 / 1 轻微色差 / 2 噪点+震动 / 3 即将崩溃
    glitch_bands = [(40, 0), (60, 1), (80, 2), (101, 3)]

    @classmethod
    def glitch_level(cls, suspicion: int) -> int:
        for threshold, level in cls.glitch_bands:
            if suspicion < threshold:
                return level
        return 3


# ---------------------------------------------------------------- 场景加载
@lru_cache(maxsize=8)
def load_scene(scene_id: str) -> dict:
    path = SCENES_DIR / f"{scene_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"未找到场景配置: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_scenes() -> list[dict]:
    out = []
    for path in sorted(SCENES_DIR.glob("*.json")):
        scene = load_scene(path.stem)
        out.append(
            {
                "scene_id": scene["scene_id"],
                "display_name": scene["display_name"],
                "target_language_label": scene["target_language_label"],
            }
        )
    return out
