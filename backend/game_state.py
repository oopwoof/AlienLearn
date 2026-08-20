"""会话状态与游戏规则。

设计原则（来自商业化文档的"状态机剥离 LLM"）：
伪装度、能量、任务阶段一律由这里的 Python 代码持有和结算。
LLM 只能"发信号"（quest_signal / emotion / severity），不能直接改数值 ——
防幻觉，也防玩家用 prompt 注入把自己的血条改满。
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field

from config import Rules


@dataclass
class TurnOutcome:
    """一轮结算的结果，同时是发给前端和写进埋点的载荷。"""

    suspicion_before: int
    suspicion_after: int
    suspicion_delta: int
    glitch_level: int
    energy: int
    stage_id: str
    stage_index: int
    stage_advanced: bool
    strikes: int
    status: str
    reasons: list[str] = field(default_factory=list)
    # 本轮首次命中的目标词（已按词表序）。空列表 = 没有新收集
    vocab_new_hits: list[str] = field(default_factory=list)
    # 能量的实际变化量（返还被 energy_start 上限截掉的部分不虚报 —— 奖励也不撒谎）
    energy_delta: int = 0


@dataclass
class Session:
    scene: dict
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)

    # 匿名玩家标识（前端 localStorage 里的 UUID）。没有它就算不出次日留存 ——
    # 而次日留存是 PRD 里假设二的原始判据（"被频繁纠错的玩家是不是留不下来"）。
    # 刻意不做账号密码：算留存只需要一个稳定的匿名 ID，不需要碰任何凭据。
    player_id: str = "anonymous"
    # A/B 分组：diorama（现状）/ text_only（隐藏箱庭）—— 验假设三（像素箱庭的 ROI）
    variant: str = "diorama"

    suspicion: int = Rules.suspicion_start
    energy: int = Rules.energy_start
    stage_index: int = 0
    stage_turns: int = 0             # 在当前阶段待了几轮，配合 min_turns_per_stage 控制节奏
    strikes: int = 0
    status: str = "playing"          # playing | crashed | won | drained
    secret_unlocked: bool = False    # 到达 intel 阶段且已建立联结 —— 老板才会松口

    turn_count: int = 0
    history: list[dict] = field(default_factory=list)   # [{"role": "player"|"npc", "text": ...}]

    # ---- 指标累计（北极星 + 验证假设用）
    target_words_total: int = 0
    turns_in_target_language: int = 0
    corrections_shown: int = 0
    glitch_events: int = 0
    out_of_scope_turns: int = 0

    # 本局已获得返能的目标词。词汇返能的去重账本：同一个词只奖一次
    vocab_used: set[str] = field(default_factory=set)
    energy_regained: int = 0     # 词汇返能实际生效的总量（被上限截掉的不计）

    # ------------------------------------------------------------ 场景视图
    @property
    def stages(self) -> list[dict]:
        return self.scene["quest"]["stages"]

    @property
    def stage(self) -> dict:
        return self.stages[min(self.stage_index, len(self.stages) - 1)]

    @property
    def stage_id(self) -> str:
        return self.stage["id"]

    def recent_history(self, turns: int = 6) -> list[dict]:
        """短时记忆流：只带最近若干轮，控制 token 也控制 NPC 的"记性"。"""
        return self.history[-turns * 2 :]

    def remember(self, role: str, text: str) -> None:
        self.history.append({"role": role, "text": text})

    # ------------------------------------------------------------ 结算
    def settle(self, *, in_scope: bool, severity: str, used_target_language: bool,
               target_words: int, quest_signal: str, revealed_secret: bool,
               vocab_candidates: list[str] | None = None) -> TurnOutcome:
        before = self.suspicion
        reasons: list[str] = []
        delta = 0

        # reasons 只写"为什么"，不带数字 —— 数字由 HUD 统一显示一次，避免正负号打架
        if not in_scope:
            delta += Rules.d_out_of_scope
            self.strikes += 1
            self.out_of_scope_turns += 1
            reasons.append("出戏 / 越狱尝试")
        elif severity == "major":
            delta += Rules.d_error_major
            reasons.append("严重语言瑕疵")
        elif severity == "minor":
            delta += Rules.d_error_minor
            reasons.append("轻微语言瑕疵")
        else:
            delta += Rules.d_clean
            reasons.append("表达自然，伪装回稳")

        if in_scope:
            # 文案承诺的是「连续 3 次出戏」——说回正题就重置。
            # 交替骚扰刷不掉：出戏 +20 / 回稳 -5，净 +15/对，suspicion 很快兜住
            self.strikes = 0

        # 任务推进由后端判定：LLM 只是投了一票，还得满足最少停留轮数
        advanced = False
        may_advance = (
            in_scope
            and quest_signal == "advance"
            and severity != "major"
            and self.stage_index < len(self.stages) - 1
            and self.stage_turns + 1 >= Rules.min_turns_per_stage
        )
        if may_advance:
            self.stage_index += 1
            self.stage_turns = 0
            advanced = True
            delta += Rules.d_stage_advance
            reasons.append(f"任务推进 → {self.stage['name']}")
        else:
            self.stage_turns += 1

        # 到了情报阶段还要再待一轮老板才肯松口：先推脱「家传的」，被追问才说。
        # 一问就给的秘密不值钱，玩家也不会记得。
        if self.stage_id == "intel" and self.stage_turns >= 1:
            self.secret_unlocked = True

        self.suspicion = max(Rules.suspicion_floor, min(Rules.suspicion_max, before + delta))

        # ---- 词汇返能：命中「本局第一次用」的目标词补充能量。
        # 门槛与北极星同款（in_scope 且用了目标语言），越狱串英文骗不到。
        # 超出单轮上限的新词不烧掉 —— 上限是限制单轮爆发，不是没收已挣的奖励。
        vocab_new_hits: list[str] = []
        refund = 0
        if in_scope and used_target_language and vocab_candidates:
            for word in vocab_candidates:
                if word in self.vocab_used:
                    continue
                if len(vocab_new_hits) >= Rules.vocab_hits_per_turn_cap:
                    break
                self.vocab_used.add(word)
                vocab_new_hits.append(word)
            refund = len(vocab_new_hits) * Rules.energy_per_vocab_hit

        energy_before = self.energy
        without_refund = max(0, self.energy - Rules.energy_per_turn)
        self.energy = min(Rules.energy_start, max(0, self.energy - Rules.energy_per_turn + refund))
        # 有效返还 = 相对「没吃词」路径实际多出来的能量，被 100 上限截掉的部分不计
        self.energy_regained += max(0, self.energy - without_refund)
        energy_delta = self.energy - energy_before

        self.turn_count += 1

        # 北极星指标防刷：越狱尝试也是一串英文，但它不是学习行为，不计入"主动目标语言输出量"
        if in_scope:
            self.target_words_total += target_words
            if used_target_language:
                self.turns_in_target_language += 1

        level = Rules.glitch_level(self.suspicion)
        if level > 0:
            self.glitch_events += 1

        if revealed_secret:
            self.status = "won"
        elif self.suspicion >= Rules.suspicion_max or self.strikes >= Rules.strikes_to_crash:
            self.status = "crashed"
        elif self.energy <= 0:
            self.status = "drained"

        return TurnOutcome(
            suspicion_before=before,
            suspicion_after=self.suspicion,
            suspicion_delta=self.suspicion - before,
            glitch_level=level,
            energy=self.energy,
            stage_id=self.stage_id,
            stage_index=self.stage_index,
            stage_advanced=advanced,
            strikes=self.strikes,
            status=self.status,
            reasons=reasons,
            vocab_new_hits=vocab_new_hits,
            energy_delta=energy_delta,
        )

    # ------------------------------------------------------------ 对外快照
    def public_state(self) -> dict:
        return {
            "session_id": self.session_id,
            "variant": self.variant,     # 前端据此决定渲不渲染箱庭
            "suspicion": self.suspicion,
            "suspicion_max": Rules.suspicion_max,
            "glitch_level": Rules.glitch_level(self.suspicion),
            "energy": self.energy,
            "energy_max": Rules.energy_start,
            "stage_index": self.stage_index,
            "stage_id": self.stage_id,
            "stage_name": self.stage["name"],
            "stage_total": len(self.stages),
            "strikes": self.strikes,
            "strikes_max": Rules.strikes_to_crash,
            "status": self.status,
            "turn_count": self.turn_count,
            "vocab_hit_count": len(self.vocab_used),
            "vocab_total": len(self.scene.get("target_vocab", [])),
        }

    def summary(self) -> dict:
        """结算屏 / 埋点用的一局总结。北极星指标就在这里。"""
        turns = max(1, self.turn_count)
        return {
            "session_id": self.session_id,
            "player_id": self.player_id,
            "variant": self.variant,
            "scene_id": self.scene["scene_id"],
            "status": self.status,
            "turns": self.turn_count,
            "duration_sec": round(time.time() - self.created_at, 1),
            # ★ 北极星：单局主动输出的目标语言量
            "target_words_total": self.target_words_total,
            "target_words_per_turn": round(self.target_words_total / turns, 1),
            "target_language_ratio": round(self.turns_in_target_language / turns, 2),
            "vocab_hits": len(self.vocab_used),
            "energy_regained": self.energy_regained,
            "corrections_shown": self.corrections_shown,
            "glitch_events": self.glitch_events,
            "out_of_scope_turns": self.out_of_scope_turns,
            "final_suspicion": self.suspicion,
            "energy_left": self.energy,
            "stage_reached": self.stage["name"],
            "stage_index": self.stage_index,
        }


VARIANTS = ("diorama", "text_only")


def assign_variant(player_id: str) -> str:
    """按 player_id 稳定分组，不用随机数。

    同一个玩家每次进来必须落在同一组，否则 A/B 的数据全是噪声 ——
    一个人今天在箱庭组、明天在纯对话组，session 时长的差异就没法归因了。
    用哈希而不是"存一份分组表"，是因为它无状态：重启、换机器、清库都不会改变分组。
    """
    if not player_id or player_id == "anonymous":
        return VARIANTS[0]
    digest = hashlib.sha256(player_id.encode("utf-8")).digest()
    return VARIANTS[digest[0] % len(VARIANTS)]


class SessionStore:
    """MVP 用内存字典即可；换 Redis 只需替换这一个类。

    进行中的对局会在重启时丢掉。这是有意接受的：一局 5-10 分钟，
    而埋点是即时落 SQLite 的，所以丢的是"进行中的手感"，不是数据。
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, scene: dict, player_id: str = "anonymous") -> Session:
        session = Session(scene=scene, player_id=player_id, variant=assign_variant(player_id))
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)


STORE = SessionStore()
