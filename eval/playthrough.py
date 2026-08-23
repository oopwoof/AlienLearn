"""整局通关评测：一局能不能在正常轮数内走完四幕。

为什么需要它（evidence-06 的教训）：单轮指标再漂亮也测不出跨轮的断裂。
live 下 Persona 经常不输出 <<<SIGNAL>>> 信号行，任务从第一天起就基本不
推进，玩家会卡在第一幕直到能量耗尽 —— 而 Router/Pedagogy 的分数当时全是
满的，因为它们只看单轮。完整对局演示走的又是 mock，于是这个 bug 活了很久。

与 redteam 的分工：redteam 打的是"标注样本逐条过管线"，局崩了会原地复活
继续跑（forced_continue）；这里打的是"一局游戏"，结束即止，量的是
turns_to_finish / 结局 / 幕推进时间线 / 信号来源分布。

用法：
    python eval/playthrough.py --scene flower_en            # mock，1 局
    MOCK_LLM=0 python eval/playthrough.py --scene flower_en --runs 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))

import orchestrator                       # noqa: E402
from config import load_scene             # noqa: E402
from game_state import Session            # noqa: E402
from llm import CLIENT                    # noqa: E402
from playthrough_scripts import script_for  # noqa: E402

OUT = ROOT / "eval" / "out" / "traces"


async def play_once(scene: dict, lines: list[str]) -> dict:
    """打一局。channel="eval" —— 评测流量不写埋点、不吃玩家额度。"""
    session = Session(scene=scene, channel="eval")
    turns: list[dict] = []
    ended: dict | None = None
    started = time.perf_counter()

    for text in lines:
        if session.status != "playing":
            break
        turn_started = time.perf_counter()
        record: dict = {"player_text": text, "stage_before": session.stage_id}
        parts: list[str] = []

        async for event, payload in orchestrator.run_turn(session, text):
            if event == "npc_delta":
                if "first_token_sec" not in record:
                    record["first_token_sec"] = round(time.perf_counter() - turn_started, 3)
                parts.append(payload["text"])
            elif event == "npc_signal":
                # source 是信号从哪来的：marker（模型照格式输出了）/ extractor
                # （兜底提取）/ mock / default。服从率直接从这里量
                record["signal"] = payload
            elif event == "state":
                record["stage_after"] = payload["stage_id"]
                record["stage_advanced"] = payload["stage_advanced"]
                record["suspicion"] = payload["suspicion"]
                record["energy"] = payload["energy"]
                record["vocab_new_hits"] = payload["vocab_new_hits"]
            elif event == "ended":
                ended = payload

        record["npc_text"] = "".join(parts).strip()
        record["latency_sec"] = round(time.perf_counter() - turn_started, 3)
        turns.append(record)

    # 台词用完了还在进行中：不是通关失败，是脚本不够长 —— 必须分开记，
    # 否则会把"评测台词写短了"误读成"玩家过不了关"
    status = ended["status"] if ended else "stalled"
    sources = Counter(t.get("signal", {}).get("source", "missing") for t in turns)

    return {
        "status": status,
        "turns_to_finish": len(turns) if ended else None,
        "lines_available": len(lines),
        "stage_timeline": [t["stage_after"] for t in turns if "stage_after" in t],
        "advanced_on_turns": [i for i, t in enumerate(turns, 1) if t.get("stage_advanced")],
        "signal_sources": dict(sources),
        "ended": ended,
        "summary": session.summary(),
        "duration_sec": round(time.perf_counter() - started, 1),
        "turns": turns,
    }


def check(scene_id: str, run: dict) -> list[str]:
    """整局的最低验收。返回问题列表（空 = 通过）。

    分级是刻意的：mock 对未注册场景只给通用兜底台词（这是既定决定，
    别为了让 mock 全绿去写台词库），所以 mock 下只验"链路不炸、能推进"，
    "能通关"只对有台词库的场景要求。
    """
    problems = []
    if run["status"] == "stalled":
        problems.append("台词用完仍未结束 —— 脚本太短或任务推不动")
    if run["status"] == "crashed":
        problems.append(f"崩盘收场（{run['summary'].get('crash_reason')}）")
    if not run["advanced_on_turns"]:
        problems.append("整局零次幕推进 —— 信号链路可能又断了（见 evidence-06）")
    if run["signal_sources"].get("missing"):
        problems.append(f"{run['signal_sources']['missing']} 轮没有信号事件")
    return problems


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", default="flower_en")
    parser.add_argument("--runs", type=int, default=0, help="默认 mock 1 局 / live 3 局")
    args = parser.parse_args()

    scene = load_scene(args.scene)
    lines = script_for(args.scene)
    runs = args.runs or (3 if CLIENT.live else 1)

    print(f"链路 {CLIENT.mode} · 场景 {args.scene} · {runs} 局 · 脚本 {len(lines)} 句")
    results = []
    for n in range(1, runs + 1):
        run = await play_once(scene, lines)
        results.append(run)
        problems = check(args.scene, run)
        mark = "✓" if not problems else "✗"
        finish = run["turns_to_finish"] or f">{len(run['turns'])}"
        print(f"  {mark} 第 {n} 局 {run['status']} · {finish} 轮 · "
              f"幕推进于 {run['advanced_on_turns']} · 信号 {run['signal_sources']} · "
              f"★{run['summary']['target_words_total']} 词")
        for p in problems:
            print(f"      ! {p}")

    won = sum(1 for r in results if r["status"] == "won")
    finished = [r["turns_to_finish"] for r in results if r["turns_to_finish"]]
    print(f"\n通关 {won}/{runs}" + (f" · 平均 {sum(finished) / len(finished):.1f} 轮" if finished else ""))

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%m%d-%H%M")
    path = OUT / f"{args.scene}__playthrough__{CLIENT.mode}__{stamp}.json"
    path.write_text(json.dumps({
        "suite": "playthrough",
        "scene_id": args.scene,
        "target_language": scene["target_language"],
        "llm_mode": CLIENT.mode,
        "model": CLIENT.model if CLIENT.live else "mock-rules",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "runs": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ↳ {path.relative_to(ROOT)}")

    # 全部失败才算脚本失败：live 下偶发一局不通关是信息，不是故障
    return 0 if won or not CLIENT.live else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
