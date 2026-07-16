"""Tests for the deterministic trading-discipline engine."""

from web.discipline import DEFAULT_PROFILE, evaluate_trade


def test_emotional_averaging_down_is_blocked() -> None:
    result = evaluate_trade(
        {
            "action": "加仓",
            "reason": "朋友说可以买，跌多了想摊低成本回本",
            "evidence": "",
            "invalidation": "",
            "emotion": "急于回本",
            "position_pct": 60,
            "add_count": 3,
            "price_move_pct": 0,
        },
        DEFAULT_PROFILE,
    )

    assert result["verdict"].startswith("红灯")
    assert result["score"] >= 8
    assert any("仓位" in item for item in result["blockers"])


def test_calm_observation_can_enter_research() -> None:
    result = evaluate_trade(
        {
            "action": "观察",
            "reason": "等待财报和板块趋势确认",
            "evidence": "公司公告和财务数据",
            "invalidation": "基本面恶化时重新评估",
            "emotion": "平静",
            "position_pct": 20,
            "add_count": 0,
            "price_move_pct": 0,
        },
        DEFAULT_PROFILE,
    )

    assert result["verdict"].startswith("绿灯")
    assert result["score"] == 0
