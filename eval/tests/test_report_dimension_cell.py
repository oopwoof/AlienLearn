"""主观三维表格的单元格：均值会把「偶尔崩一轮」稀释掉。

人设维锚点标定（eval/anchors.py）量出来：裁判在这一维上几乎是二值的 ——
32 条样本里 30 条不是 5 就是 1，rubric 里写的「3 = 偏客服腔」那一档根本没被用上。

于是均值成了很差的汇总量：56 轮里崩一轮，均值 4.93，摆在一片 5.00 中间
看上去像没事。表格必须把低分轮数摆到脸上。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))

import report  # noqa: E402


def test_clean_run_shows_just_the_mean():
    assert report.dimension_cell([5] * 56) == "5.00"


def test_one_break_in_a_long_trace_is_visible_in_the_cell():
    cell = report.dimension_cell([5] * 55 + [1])
    assert "4.93" in cell
    assert "1" in cell.replace("4.93", ""), "一轮崩了却只剩个均值，等于没报"


def test_cell_counts_every_turn_below_four():
    cell = report.dimension_cell([5] * 10 + [1, 2, 3])
    assert "3" in cell.replace("4.", "")


def test_empty_dimension_does_not_crash():
    assert report.dimension_cell([]) == "—"
