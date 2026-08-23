"""测试装置：导入路径、强制 mock 链路、埋点库隔离。"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 必须在 import config 之前设：Settings 的字段是 import 时求值的，
# 而 load_dotenv 不会覆盖已存在的环境变量。没有这行，本机 .env（MOCK_LLM=0 + 真 key）
# 会让单测去打真实模型 —— 慢、花钱、还不确定。
os.environ["MOCK_LLM"] = "1"

import telemetry  # noqa: E402 —— 必须在 sys.path 与 env 就位之后


@pytest.fixture(autouse=True)
def isolated_telemetry(tmp_path, monkeypatch):
    """每个测试一个独立的空埋点库。

    autouse 是刻意的：测试写进 data/telemetry.db 会污染北极星，
    而这种污染发现不了 —— 指标只是慢慢变得不像真的。靠"每个测试自己记得
    monkeypatch"迟早会漏，所以在这里一次性堵死。

    只 patch 路径不够：_conn 是模块级懒单例，一旦建过连接就再也不看路径了。
    """
    monkeypatch.setattr(telemetry, "_DB_PATH", tmp_path / "telemetry.db")
    monkeypatch.setattr(telemetry, "_conn", None)
    yield
    conn = telemetry._conn
    if conn is not None:
        conn.close()
    telemetry._conn = None
