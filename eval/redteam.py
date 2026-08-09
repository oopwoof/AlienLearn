"""红蓝对抗测试机：把三类模拟玩家跑过完整管线，落成可复现的对话 trace。

    python eval/redteam.py                    # 三个套件都跑
    python eval/redteam.py --suite jailbreak  # 只跑越狱
    python eval/redteam.py --scene ramen_ja   # 换语言层

产出 eval/out/traces/{scene}__{suite}__{mode}__{ts}.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))

import orchestrator                       # noqa: E402
from agents import CLIENT                 # noqa: E402
from config import load_scene             # noqa: E402
from game_state import Session            # noqa: E402
from suites import SUITES                 # noqa: E402

OUT = ROOT / "eval" / "out" / "traces"


async def run_turn(session: Session, sample: dict) -> dict:
    """跑一轮，把每个 Agent 的产出原样收下来。"""
    record: dict = {
        "player_text": sample["text"],
        "expect_in_scope": sample["expect_in_scope"],
        "expect_severity": sample.get("expect_severity"),
        "note": sample.get("note", ""),
        "stage_before": session.stage_id,
        "npc_text": "",
    }
    started = time.perf_counter()
    parts: list[str] = []

    async for event, payload in orchestrator.run_turn(session, sample["text"]):
        if event == "npc_delta":
            if "first_token_sec" not in record:
                record["first_token_sec"] = round(time.perf_counter() - started, 3)
            parts.append(payload["text"])
        elif event == "route":
            record["route"] = payload
        elif event == "pedagogy":
            record["pedagogy"] = payload
        elif event == "npc_signal":
            record["signal"] = payload
        elif event == "state":
            record["state"] = payload
        elif event == "ended":
            record["ended"] = {"status": payload["status"]}

    record["npc_text"] = "".join(parts).strip()
    record["latency_sec"] = round(time.perf_counter() - started, 3)
    return record


async def run_suite(scene: dict, suite_name: str) -> dict:
    samples = SUITES[suite_name]
    session = Session(scene=scene)
    turns = []

    for sample in samples:
        record = await run_turn(session, sample)

        # 评测台要跑完全部标注样本，所以记录结局后让会话继续。
        # 这不是玩家会话 —— 玩家那边该崩就崩。
        if session.status != "playing":
            record["forced_continue"] = session.status
            session.status = "playing"
            session.strikes = 0
            session.energy = max(session.energy, 30)

        turns.append(record)

    return {
        "suite": suite_name,
        "scene_id": scene["scene_id"],
        "target_language": scene["target_language"],
        "llm_mode": CLIENT.mode,
        "model": CLIENT.model if CLIENT.live else "mock-rules",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "turns": turns,
        "session_summary": session.summary(),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", default="ramen_en")
    parser.add_argument("--suite", choices=[*SUITES, "all"], default="all")
    args = parser.parse_args()

    scene = load_scene(args.scene)
    names = list(SUITES) if args.suite == "all" else [args.suite]

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%m%d-%H%M")

    print(f"链路 {CLIENT.mode}" + (f" ({CLIENT.model})" if CLIENT.live else " (规则桩)"))
    for name in names:
        print(f"\n▸ 跑套件 {name} ({len(SUITES[name])} 条样本) …")
        trace = await run_suite(scene, name)

        blocked = sum(1 for t in trace["turns"] if not t.get("route", {}).get("in_scope", True))
        expected_block = sum(1 for t in trace["turns"] if not t["expect_in_scope"])
        avg_latency = round(sum(t["latency_sec"] for t in trace["turns"]) / len(trace["turns"]), 2)
        print(f"  拦截 {blocked} / 应拦 {expected_block} · 平均延迟 {avg_latency}s")

        path = OUT / f"{args.scene}__{name}__{CLIENT.mode}__{stamp}.json"
        path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  → {path.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
