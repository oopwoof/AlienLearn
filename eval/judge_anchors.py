"""拿人设锚点样本去标定裁判。

    python eval/judge_anchors.py                 # 只跑 dev（默认）
    python eval/judge_anchors.py --split holdout # rubric 定稿后才跑
    python eval/judge_anchors.py --split all

**默认只跑 dev 是有意的**：holdout 是留出集，改 rubric 期间一眼都不该看，
跟 boundary 同一条纪律。要看必须显式敲出来 —— 让破戒成为一个动作，
而不是一个默认值。

退出码：全部 hard 与 clean 落进分带 → 0，否则 → 1。
所以它可以直接当回归闸用：哪天有人把人设 rubric 改松了，这里会红。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))

import anchors                              # noqa: E402
import judge                                # noqa: E402
from llm import CLIENT                      # noqa: E402

OUT = ROOT / "eval" / "out"

_KIND_LABEL = {"clean": "好好说话", "soft": "软伤", "hard": "硬伤"}


def _bucket_line(result: dict, kind: str) -> str:
    b = result[kind]
    scores = "/".join(str(s) for s in b["scores"])
    return f"| {_KIND_LABEL[kind]} | {b['hit']}/{b['total']} | {anchors.BANDS[kind]} | {scores} |"


def render_report(results: list[dict]) -> str:
    """把标定结果写成一份能直接读的 markdown。

    最要紧的是第一段就把结论说死 —— 这份报告存在的唯一理由是回答
    「人设维会不会扣分」，读者不该需要自己去表格里数。"""
    hard_hit = sum(r["hard"]["hit"] for r in results)
    hard_total = sum(r["hard"]["total"] for r in results)
    clean_hit = sum(r["clean"]["hit"] for r in results)
    clean_total = sum(r["clean"]["total"] for r in results)
    soft_hit = sum(r["soft"]["hit"] for r in results)
    soft_total = sum(r["soft"]["total"] for r in results)
    mode = results[0].get("judge_mode") if results else "?"

    if hard_hit == 0 and hard_total:
        verdict = ("**结论：这一维不会扣分。** 所有硬伤样本都拿了分带外的分 —— "
                   "真实 trace 上那些 5.00 是 rubric 的产物，不是 Persona 的战果，"
                   "不能再拿它当证据。")
    elif hard_hit < hard_total:
        verdict = (f"**结论：这一维扣分但不彻底** —— {hard_total} 条硬伤里漏掉 "
                   f"{hard_total - hard_hit} 条。漏掉的那几类见下表，"
                   "它们是 rubric 里没写进去的出戏方式。")
    elif clean_hit < clean_total:
        verdict = (f"**结论：会扣分，但误伤好回复** —— {clean_total} 条正常回复里有 "
                   f"{clean_total - clean_hit} 条被判进了低分带。只罚漏报不罚误报是自欺，"
                   "这一半同样不合格。")
    else:
        verdict = ("**结论：这一维会扣分，也不误伤。** 硬伤全部落进 1-2 分，"
                   "正常回复全部保住 4-5 分 —— 真实 trace 上的 5.00 可以当战果读了。")

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    splits = "、".join(sorted({r["split"] for r in results}))
    lines = [
        "# 人设维锚点标定",
        "",
        f"时间：{stamp} · 裁判：{mode} · 样本集：{splits}",
        "",
        verdict,
        "",
        f"硬伤命中 {hard_hit}/{hard_total} · 好好说话命中 {clean_hit}/{clean_total} "
        f"· 软伤命中 {soft_hit}/{soft_total}（软伤只报不卡）",
        "",
    ]

    for r in results:
        lines += [
            f"## {r['scene_id']} · {r['split']}",
            "",
            "| 类别 | 命中 | 应落分带 | 实得分 |",
            "| --- | --- | --- | --- |",
            *[_bucket_line(r, k) for k in ("clean", "soft", "hard")],
            "",
        ]

        slipped = [row for row in r["rows"] if row["kind"] == "hard" and not row["hit"]]
        if slipped:
            lines += ["**漏掉的硬伤**（裁判给了分带外的分）：", ""]
            for row in slipped:
                lines += [
                    f"- 第 {row['index']} 轮 · `{row['mode']}` · 得 {row['score']} 分"
                    f"（应 {row['band'][0]}-{row['band'][1]}）",
                    f"  - NPC：{row['npc_text']}",
                    f"  - 该扣的理由：{row['why']}",
                    f"  - 裁判的说法：{row['reason'] or '（无）'}",
                ]
            lines.append("")

        false_alarms = [row for row in r["rows"] if row["kind"] == "clean" and not row["hit"]]
        if false_alarms:
            lines += ["**误伤的好回复**：", ""]
            for row in false_alarms:
                lines += [
                    f"- 第 {row['index']} 轮 · `{row['mode']}` · 得 {row['score']} 分"
                    f"（应 {row['band'][0]}-{row['band'][1]}）",
                    f"  - NPC：{row['npc_text']}",
                    f"  - 裁判的说法：{row['reason'] or '（无）'}",
                ]
            lines.append("")

    return "\n".join(lines)


async def run(splits: list[str] | None) -> list[dict]:
    results = []
    for trace in anchors.build_traces(splits=splits):
        if CLIENT.live:
            judgment = await judge.judge_with_model(trace)
        else:
            judgment = judge.judge_heuristically(trace)
        result = anchors.score(trace, judgment)
        results.append(result)

        b = result["hard"]
        print(f"  {trace['scene_id']} · {trace['split']}：硬伤 {b['hit']}/{b['total']}"
              f" · 好好说话 {result['clean']['hit']}/{result['clean']['total']}"
              f" · 软伤 {result['soft']['hit']}/{result['soft']['total']}")
    return results


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "holdout", "all"], default="dev",
                        help="默认只跑 dev；holdout 是留出集，要看必须显式指定")
    args = parser.parse_args()
    splits = None if args.split == "all" else [args.split]

    if not CLIENT.live:
        print("⚠ 无 API key，用启发式打分器标定 —— 量的是兜底路径，不是裁判模型。")

    results = await run(splits)
    if not results:
        print("没有匹配的锚点样本")
        return 1

    text = render_report(results)
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"anchor-calibration-{args.split}-{datetime.now():%m%d-%H%M}.md"
    (OUT / name).write_text(text, encoding="utf-8")
    (OUT / f"anchor-calibration-{args.split}.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 eval/out/{name}")

    passed = all(r["passed"] for r in results)
    print("通过" if passed else "未通过：见报告里漏掉的硬伤 / 误伤的好回复")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
