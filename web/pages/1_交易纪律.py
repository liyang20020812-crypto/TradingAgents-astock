"""Trading discipline dashboard for personal A-share decisions."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from web.discipline import append_journal, evaluate_trade, load_profile, save_profile

st.set_page_config(page_title="交易纪律防火墙", page_icon="🛡️", layout="wide")

st.title("🛡️ 交易纪律防火墙")
st.caption("先检查动机、仓位和失效条件，再进入股票分析。这里不会替你下单。")

profile = load_profile()
settings = profile.setdefault("settings", {})
holdings = profile.setdefault("holdings", [])

with st.expander("当前核心规则", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    max_single = c1.number_input(
        "单股仓位上限（%）",
        min_value=1.0,
        max_value=100.0,
        value=float(settings.get("max_single_stock_pct", 35.0)),
        step=1.0,
    )
    max_sector = c2.number_input(
        "同板块仓位上限（%）",
        min_value=1.0,
        max_value=100.0,
        value=float(settings.get("max_sector_pct", 55.0)),
        step=1.0,
    )
    max_add = c3.number_input(
        "最多加仓次数",
        min_value=0,
        max_value=20,
        value=int(settings.get("max_add_times", 2)),
        step=1,
    )
    cooldown = c4.number_input(
        "冲动交易冷静期（分钟）",
        min_value=0,
        max_value=240,
        value=int(settings.get("cooldown_minutes", 15)),
        step=5,
    )

st.subheader("个人持仓")
columns = ["ticker", "name", "shares", "cost", "sector"]
frame = pd.DataFrame(holdings, columns=columns)
edited = st.data_editor(
    frame,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "ticker": st.column_config.TextColumn("股票代码"),
        "name": st.column_config.TextColumn("股票名称"),
        "shares": st.column_config.NumberColumn("持股数量", min_value=0, step=100),
        "cost": st.column_config.NumberColumn("持仓成本", min_value=0.0, format="%.3f"),
        "sector": st.column_config.TextColumn("相关板块"),
    },
    hide_index=True,
)

if st.button("保存持仓和规则", type="primary"):
    profile["settings"] = {
        "max_single_stock_pct": float(max_single),
        "max_sector_pct": float(max_sector),
        "max_add_times": int(max_add),
        "cooldown_minutes": int(cooldown),
    }
    profile["holdings"] = edited.fillna("").to_dict(orient="records")
    save_profile(profile)
    st.success("已保存到本机私有数据目录，不会写入GitHub仓库。")

st.divider()
st.subheader("买卖前强制复核")

with st.form("trade_review"):
    left, right = st.columns(2)
    ticker = left.text_input("准备操作的股票", placeholder="600487 亨通光电")
    action = left.selectbox("准备做什么", ["观察", "买入", "加仓", "减仓", "卖出", "清仓", "做T"])
    emotion = left.selectbox("你现在的真实情绪", ["平静", "焦虑", "害怕踏空", "急于回本", "兴奋", "愤怒"])
    price_move_pct = left.number_input("该股今天已涨跌（%）", value=0.0, step=0.5)

    position_pct = right.number_input("操作后预计单股仓位（%）", min_value=0.0, max_value=100.0, value=0.0)
    add_count = right.number_input("这已经是第几次加仓", min_value=0, max_value=50, value=0, step=1)
    reason = right.text_area("为什么现在想操作？", placeholder="不要只写‘感觉会涨’或‘想回本’")
    evidence = st.text_area("有哪些新增、可验证的证据？", placeholder="公告、财报、订单、板块趋势、量价结构等")
    invalidation = st.text_area("什么情况证明你错了？错了以后怎么处理？")

    submitted = st.form_submit_button("检查这笔交易", type="primary", use_container_width=True)

if submitted:
    plan = {
        "ticker": ticker,
        "action": action,
        "emotion": emotion,
        "price_move_pct": price_move_pct,
        "position_pct": position_pct,
        "add_count": add_count,
        "reason": reason,
        "evidence": evidence,
        "invalidation": invalidation,
    }
    result = evaluate_trade(plan, profile)
    append_journal({**plan, "result": result})

    if result["verdict"].startswith("红灯"):
        st.error(f"{result['verdict']}｜风险分 {result['score']}")
    elif result["verdict"].startswith("黄灯"):
        st.warning(f"{result['verdict']}｜风险分 {result['score']}")
    else:
        st.success(f"{result['verdict']}｜风险分 {result['score']}")

    if result["blockers"]:
        st.markdown("#### 当前拦截原因")
        for item in result["blockers"]:
            st.write(f"- {item}")

    st.markdown("#### 你必须回答的反问")
    for question in result["questions"]:
        st.write(f"- {question}")

    st.info(
        "绿灯也不等于可以买卖，只代表可以进入正式研究；红灯时默认先执行冷静期，禁止继续补仓或追涨。"
    )
