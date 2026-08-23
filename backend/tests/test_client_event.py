"""前端埋点端点。

这条路径存在的理由：手机内测者不会开控制台，只 console.warn 的前端故障
（比如 span 高亮匹配失败）等于没发生。所以它必须真的落库 —— 也必须
只落白名单里的类型，否则就成了任意数据的倾倒口。

超长载荷的截断行为原本只由 e2e 脚本覆盖（靠查真库断言行数）；写入闸上线后
自测流量不再落库，那条断言没了着落，所以下沉到这里。
"""

import json

import pytest
from fastapi.testclient import TestClient

import main
import telemetry
from config import load_scene
from game_state import STORE


@pytest.fixture
def client():
    return TestClient(main.app)


def _new_session(player_id: str = "a3f9c1d24b8e") -> str:
    return STORE.create(load_scene("ramen_en"), player_id=player_id).session_id


def _logged(event_type: str) -> list[dict]:
    return [json.loads(r["payload"]) for r in telemetry.db().execute(
        "SELECT payload FROM events WHERE event_type=?", (event_type,))]


def test_whitelisted_event_is_logged(client):
    sid = _new_session()
    res = client.post("/api/client_event", json={
        "session_id": sid, "type": "span_match_failed", "payload": {"span": "xx", "turn": 1}})
    assert res.status_code == 200
    assert _logged("client_span_match_failed") == [{"span": "xx", "turn": 1}]


def test_unknown_type_is_rejected(client):
    sid = _new_session()
    res = client.post("/api/client_event", json={
        "session_id": sid, "type": "evil_type", "payload": {}})
    assert res.status_code == 422
    assert _logged("client_evil_type") == []


def test_unknown_session_is_rejected(client):
    res = client.post("/api/client_event", json={
        "session_id": "nope", "type": "span_match_failed", "payload": {}})
    assert res.status_code == 404


def test_oversized_payload_is_truncated_not_stored(client):
    """2KB 上限：超了就只留一个标记。埋点库不该被前端塞进任意大小的数据。"""
    sid = _new_session()
    res = client.post("/api/client_event", json={
        "session_id": sid, "type": "span_match_failed", "payload": {"junk": "x" * 5000}})
    assert res.status_code == 200
    assert _logged("client_span_match_failed") == [{"truncated": True}]


def test_feedback_is_whitelisted_and_logged(client):
    """结算屏的星级+一句话。内测者不会为了一句话去加微信，但会顺手点个星。"""
    sid = _new_session()
    res = client.post("/api/client_event", json={
        "session_id": sid, "type": "feedback",
        "payload": {"stars": 4, "text": "第三幕有点卡", "status": "won"}})
    assert res.status_code == 200
    assert _logged("client_feedback") == [{"stars": 4, "text": "第三幕有点卡", "status": "won"}]


def test_eval_channel_session_does_not_log(client):
    """自测脚本走 HTTP 上报也不落库 —— 与 turn/session_end 同一道闸。"""
    sid = _new_session(player_id="e2e_stage3")
    res = client.post("/api/client_event", json={
        "session_id": sid, "type": "span_match_failed", "payload": {"span": "xx"}})
    assert res.status_code == 200
    assert res.json()["logged"] is False
    assert _logged("client_span_match_failed") == []
