from __future__ import annotations

import streamlit as st
from utils.portfolio import (
    load_portfolio, save_portfolio,
    add_to_group, remove_from_group, add_to_home_watch,
    sync_holdings_to_groups, move_group,
)
from utils.stock_data import get_stock_info, format_price, format_price_md, format_volume

st.set_page_config(page_title="台股", page_icon="🇹🇼", layout="wide")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
portfolio = st.session_state.portfolio

# Auto-sync 持有 group with both profiles' holdings
if sync_holdings_to_groups(portfolio):
    save_portfolio(portfolio)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🇹🇼 台股管理")
    groups = list(portfolio.get("tw_groups", {}).keys())

    with st.expander("➕ 新增群組"):
        new_group = st.text_input("群組名稱", key="tw_new_group", placeholder="例：長期持有")
        if st.button("建立", key="tw_btn_grp", use_container_width=True):
            name = new_group.strip()
            if name and name not in portfolio["tw_groups"]:
                portfolio["tw_groups"][name] = []
                save_portfolio(portfolio)
                st.rerun()

    with st.expander("➕ 新增股票"):
        raw = st.text_input("代號（不需加 .TW）", placeholder="例: 2330", key="tw_raw")
        tgt = st.selectbox("加入群組", groups, key="tw_tgt")
        if st.button("新增", key="tw_btn_add", use_container_width=True):
            ticker = raw.strip().upper()
            if ticker and not ticker.endswith(".TW"):
                ticker += ".TW"
            if ticker and add_to_group(portfolio, ticker, tgt, "tw"):
                save_portfolio(portfolio)
                st.rerun()

    with st.expander("↕️ 群組排序"):
        groups_now = list(portfolio.get("tw_groups", {}).keys())
        for i, grp in enumerate(groups_now):
            c_name, c_up, c_dn = st.columns([6, 1, 1])
            c_name.markdown(
                f"<div style='padding:4px 0;font-size:0.9em'>{grp}</div>",
                unsafe_allow_html=True,
            )
            if c_up.button("↑", key=f"tw_up_{grp}", disabled=(i == 0),
                           use_container_width=True):
                move_group(portfolio, grp, -1, "tw")
                save_portfolio(portfolio)
                st.rerun()
            if c_dn.button("↓", key=f"tw_dn_{grp}",
                           disabled=(i == len(groups_now) - 1),
                           use_container_width=True):
                move_group(portfolio, grp, 1, "tw")
                save_portfolio(portfolio)
                st.rerun()

    if st.button("🔄 重新整理報價", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
st.header("🇹🇼 台股")

group_names = list(portfolio.get("tw_groups", {}).keys())
if not group_names:
    st.info("尚未建立任何群組，請從左側新增。")
    st.stop()

tabs = st.tabs(group_names)

COLS = 3   # cards per row

def _rt_badge(info: dict) -> str:
    if "TWSE" in info.get("data_source", ""):
        return (
            "<span style='font-size:0.62em;background:rgba(34,197,94,0.13);"
            "color:#22c55e;padding:1px 5px;border-radius:3px;"
            "margin-left:4px;vertical-align:middle'>即時</span>"
        )
    return ""


def render_tw_card(ticker: str, grp: str):
    info = get_stock_info(ticker)
    actual_ticker = ticker
    if not info and ticker.endswith(".TW"):
        alt = ticker.replace(".TW", ".TWO")
        info = get_stock_info(alt)
        if info:
            actual_ticker = alt

    if not info:
        with st.container(border=True):
            st.caption(f"⚠️ {ticker}")
            st.caption("無法載入報價")
            if st.button("✕", key=f"tw_rm_err_{ticker}_{grp}",
                         type="secondary", use_container_width=True):
                remove_from_group(portfolio, ticker, grp, "tw")
                save_portfolio(portfolio)
                st.rerun()
        return

    sign = "▲" if info["change"] >= 0 else "▼"
    clr  = "#ff4b4b" if info["change"] >= 0 else "#21c55d"
    price_str = format_price(info["price"], True)

    with st.container(border=True):
        # ── Compact price block ───────────────────────────────────────────
        st.markdown(
            f"<div style='margin-bottom:6px'>"
            f"<div class='stock-card-name'>{info['label']}{_rt_badge(info)}</div>"
            f"<div style='font-size:1.35em;font-weight:700;line-height:1.15'>"
            f"{price_str}</div>"
            f"<div style='font-size:0.84em;font-weight:600;color:{clr};margin-top:2px'>"
            f"{sign}&thinsp;{abs(info['change']):.2f}（{info['change_pct']:+.2f}%）"
            f"</div></div>",
            unsafe_allow_html=True,
        )

        # ── 52-week range bar ─────────────────────────────────────────────
        if info.get("week_52_high") and info.get("week_52_low"):
            lo, hi = info["week_52_low"], info["week_52_high"]
            ratio = (info["price"] - lo) / (hi - lo) if hi > lo else 0.5
            pct = min(max(ratio * 100, 0), 100)
            st.markdown(
                f"<div style='margin:5px 0 3px'>"
                f"<div style='height:3px;border-radius:2px;"
                f"background:rgba(128,128,128,0.18);overflow:hidden'>"
                f"<div style='height:100%;width:{pct:.0f}%;"
                f"background:#4dabf5;border-radius:2px'></div></div>"
                f"<div class='stock-card-caption'>年位置 {pct:.0f}%"
                f"　{format_price(lo, True)} – {format_price(hi, True)}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── 昨收 + Volume ──────────────────────────────────────────────────
        prev = info.get("prev_close")
        meta = []
        if prev is not None:
            meta.append(f"昨收 {format_price(prev, True)}")
        meta.append(f"量 {format_volume(info['volume'])}")
        st.markdown(
            f"<div class='stock-card-caption'>{'　'.join(meta)}</div>",
            unsafe_allow_html=True,
        )

        # ── Action buttons ────────────────────────────────────────────────
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button("🔍", key=f"tw_det_{ticker}_{grp}",
                         use_container_width=True, help="查看個股"):
                st.session_state.detail_ticker = actual_ticker
                st.switch_page("pages/7_個股詳細資訊.py")
        with b2:
            if st.button("💼", key=f"tw_hold_{ticker}_{grp}",
                         use_container_width=True, help="加入持有"):
                portfolio["tw_groups"].setdefault("持有", [])
                add_to_group(portfolio, ticker, "持有", "tw")
                save_portfolio(portfolio)
                st.toast(f"{info['display_name']} 已加入「持有」")
        with b3:
            if st.button("🏠", key=f"tw_home_{ticker}_{grp}",
                         use_container_width=True, help="首頁追蹤"):
                if add_to_home_watch(portfolio, ticker):
                    save_portfolio(portfolio)
                    st.toast(f"{info['display_name']} 已加入首頁追蹤")
                else:
                    st.toast("已在首頁追蹤中")
        with b4:
            if st.button("❌", key=f"tw_rm_{ticker}_{grp}",
                         use_container_width=True, type="secondary", help="取消收藏"):
                remove_from_group(portfolio, ticker, grp, "tw")
                save_portfolio(portfolio)
                st.rerun()


for tab, grp in zip(tabs, group_names):
    with tab:
        tickers = portfolio["tw_groups"].get(grp, [])
        if not tickers:
            st.caption("此群組尚無股票。")
            continue

        for row_start in range(0, len(tickers), COLS):
            row = tickers[row_start : row_start + COLS]
            cols = st.columns(COLS)
            for i, ticker in enumerate(row):
                with cols[i]:
                    render_tw_card(ticker, grp)
