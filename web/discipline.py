"""Deterministic trading-discipline checks and local-only profile storage."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_LOCAL = _ROOT / ".local"
_PROFILE = _LOCAL / "trading_profile.json"
_JOURNAL = _LOCAL / "trade_journal.jsonl"

DEFAULT_PROFILE: dict[str, Any] = {
    "settings": {
        "max_single_stock_pct": 35.0,
        "max_sector_pct": 55.0,
        "max_add_times": 2,
        "cooldown_minutes": 15,
    },
    "holdings": [
        {"ticker": "600487", "name": "亨通光电", "shares": 1700, "cost": 104.386, "sector": "通信/海缆"},
        {"ticker": "600522", "name": "中天科技", "shares": 200, "cost": 64.951, "sector": "通信/海缆"},
    ],
}


def load_profile() -> dict[str, Any]:
    if not _PROFILE.exists():
        return deepcopy(DEFAULT_PROFILE)
    try:
        data = json.loads(_PROFILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else deepcopy(DEFAULT_PROFILE)
    except (OSError, json.JSONDecodeError):
        return deepcopy(DEFAULT_PROFILE)


def save_profile(profile: dict[str, Any]) -> None:
    _LOCAL.mkdir(parents=True, exist_ok=True)
    _PROFILE.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")


def append_journal(entry: dict[str, Any]) -> None:
    _LOCAL.mkdir(parents=True, exist_ok=True)
    payload = {"created_at": datetime.now().isoformat(timespec="seconds"), **entry}
    with _JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def evaluate_trade(plan: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Return a conservative risk verdict without calling an LLM."""
    score = 0
    blockers: list[str] = []
    questions: list[str] = []

    action = str(plan.get("action", "观察"))
    reason = str(plan.get("reason", "")).strip()
    evidence = str(plan.get("evidence", "")).strip()
    invalidation = str(plan.get("invalidation", "")).strip()
    emotion = str(plan.get("emotion", "平静"))
    position_pct = float(plan.get("position_pct", 0) or 0)
    add_count = int(plan.get("add_count", 0) or 0)
    price_move_pct = float(plan.get("price_move_pct", 0) or 0)

    emotional_words = ("回本", "怕踏空", "朋友说", "跌多了", "应该反弹", "摊低成本", "不想卖飞", "感觉")
    if any(word in reason for word in emotional_words):
        score += 3
        blockers.append("交易理由包含回本、踏空、朋友意见或摊低成本等情绪线索。")

    if action in {"买入", "加仓"} and not evidence:
        score += 3
        blockers.append("买入或加仓没有新增、可验证的证据。")

    if action in {"买入", "加仓"} and price_move_pct >= 4:
        score += 2
        blockers.append("标的当日已明显上涨，存在追涨风险。")

    settings = profile.get("settings", {})
    if position_pct > float(settings.get("max_single_stock_pct", 35)):
        score += 4
        blockers.append("操作后单股仓位超过预设上限。")

    if action == "加仓" and add_count >= int(settings.get("max_add_times", 2)):
        score += 4
        blockers.append("已达到或超过最大加仓次数。")

    if action in {"买入", "加仓", "清仓"} and not invalidation:
        score += 2
        blockers.append("没有写出判断失效条件。")

    if emotion in {"焦虑", "害怕踏空", "急于回本", "兴奋", "愤怒"}:
        score += 3
        blockers.append(f"当前情绪为“{emotion}”，不适合立即扩大决策。")

    if action in {"卖出", "清仓"} and ("回本" in reason or "小赚" in reason):
        score += 3
        blockers.append("卖出动机可能只是解除被套压力，而非逻辑或趋势变化。")

    questions.extend([
        "假设今天没有持仓，你还会按当前价格做同样的决定吗？",
        "市场出现什么新证据，才支持这次操作？",
        "什么情况证明你错了，错了以后具体怎么处理？",
        "如果操作后股价立刻反向波动10%，你还能执行原计划吗？",
    ])

    if score >= 8:
        verdict = "红灯：暂停操作"
    elif score >= 4:
        verdict = "黄灯：冷静后复核"
    else:
        verdict = "绿灯：可进入研究阶段"

    return {"score": score, "verdict": verdict, "blockers": blockers, "questions": questions}
