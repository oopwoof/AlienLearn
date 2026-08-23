"""裁判分批：56 轮的套件必须能打分。

原来一次把整个 trace 塞进一个请求，max_tokens 要 200×轮数+400 ——
56 轮就是 11600，超过 deepseek-chat 的 8K 输出上限，请求在参数校验阶段
就被拒（400），一个字都没生成。0820 的三套 live trace 因此全部没有裁判分。

卡的是输出上限不是输入：整个 body 只有约 1 万 token，上下文绰绰有余。
所以分批只需要切请求，不需要切上下文。
"""

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))

import judge  # noqa: E402


def make_trace(n: int) -> dict:
    return {
        "scene_id": "ramen_en",
        "suite": "labeled_v2",
        "turns": [
            {"player_text": f"line {i}", "npc_text": f"reply {i}",
             "expect_in_scope": True, "expect_severity": "none",
             "stage_before": "enter", "route": {"in_scope": True, "reason": ""},
             "pedagogy": {"severity": "none", "errors": []}}
            for i in range(1, n + 1)
        ],
    }


class FakeClient:
    """记录每次调用的 max_tokens 与轮数，按 body 里的 index 原样回分。"""

    def __init__(self, fail_on: set[int] | None = None):
        self.calls: list[dict] = []
        self.fail_on = fail_on or set()

    async def json_completion(self, system, body, **kwargs):
        self.calls.append({"max_tokens": kwargs.get("max_tokens"), "body": body})
        if len(self.calls) in self.fail_on:
            raise RuntimeError("模拟的裁判调用失败")
        indexes = [int(line.split("第 ")[1].split(" 轮")[0])
                   for line in body.splitlines() if line.startswith("# 第 ")]
        return {"turns": [{"index": i, "persona_consistency": 5,
                           "pedagogy_compliance": 4, "safety": 5,
                           "reason": f"第 {i} 轮"} for i in indexes]}


@pytest.fixture
def fake(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(judge, "CLIENT", client)
    return client


def test_long_trace_is_split_into_batches(fake):
    result = asyncio.run(judge.judge_with_model(make_trace(56)))
    assert len(fake.calls) == 3                     # 20 + 20 + 16
    assert [c["max_tokens"] for c in fake.calls] == [4400, 4400, 3600]
    assert all(c["max_tokens"] <= 8000 for c in fake.calls)


def test_batch_indexes_stay_global(fake):
    """第二批的第一轮必须是"第 21 轮"，否则合并时会覆盖第一批的分。"""
    result = asyncio.run(judge.judge_with_model(make_trace(56)))
    assert [t["index"] for t in result["turns"]] == list(range(1, 57))
    assert [t["reason"] for t in result["turns"]][20] == "第 21 轮"
    assert "# 第 21 轮" in fake.calls[1]["body"]
    assert "# 第 1 轮" not in fake.calls[1]["body"]


def test_short_trace_still_one_call(fake):
    asyncio.run(judge.judge_with_model(make_trace(10)))
    assert len(fake.calls) == 1
    assert fake.calls[0]["max_tokens"] == 2400


def test_one_failing_batch_keeps_the_others(monkeypatch):
    """整 trace 全降级太浪费：坏的那一批退启发式，其余保留模型分。"""
    client = FakeClient(fail_on={2})
    monkeypatch.setattr(judge, "CLIENT", client)
    result = asyncio.run(judge.judge_with_model(make_trace(56)))
    assert result["degraded_batches"] == [2]
    assert result["judge_mode"] == "model"
    assert len(result["turns"]) == 56
    # 第一批仍是模型给的评语，第二批退回启发式的措辞
    assert result["turns"][0]["reason"] == "第 1 轮"
    assert result["turns"][0]["reason"] != result["turns"][25]["reason"]
