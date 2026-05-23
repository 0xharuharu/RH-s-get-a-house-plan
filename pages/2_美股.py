from __future__ import annotations

import streamlit as st
from utils.portfolio import load_portfolio, save_portfolio, add_to_group, remove_from_group, add_to_home_watch
from utils.stock_data import get_stock_info, format_price, format_price_md, format_volume

st.set_page_config(page_title="美股", page_icon="🇺🇸", layout="wide")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
portfolio = st.session_state.portfolio

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🇺🇸 美股管理")
    groups = list(portfolio.get("us_groups", {}).keys())

    with st.expander("➕ 新增群組"):
        new_group = st.text_input("群組名稱", key="us_new_group", placeholder="例：成長股")
        if st.button("建立", key="us_btn_grp", use_container_width=True):
            name = new_group.strip()
            if name and name not in portfolio["us_groups"]:
                portfolio["us_groups"][name] = []
                save_portfolio(portfolio)
                st.rerun()

    with st.expander("➕ 新增股票"):
        raw = st.text_input("代號", placeholder="例: NVDA", key="us_raw")
        tgt = st.selectbox("加入群組", groups, key="us_tgt")
        if st.button("新增", key="us_btn_add", use_container_width=True):
            ticker = raw.strip().upper()
            if ticker and add_to_group(portfolio, ticker, tgt, "us"):
                save_portfolio(portfolio)
                st.rerun()

    if st.button("🔄 重新整理報價", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Main ─────────────────────────────────────────────────────────────────────
st.title("🇺🇸 美股")

group_names = list(portfolio.get("us_groups", {}).keys())
if not group_names:
    st.info("尚未建立任何群組，請從左側新增。")
    st.stop()

tabs = st.tabs(group_names)

for tab, grp in zip(tabs, group_names):
    with tab:
        tickers = portfolio["us_groups"].get(grp, [])
        if not tickers:
            st.caption("此群組尚無股票。")
            continue

        n = min(len(tickers), 4)
        cols = st.columns(n)

        for i, ticker in enumerate(tickers):
            with cols[i % n]:
                info = get_stock_info(ticker)
                if not info:
                    st.error(f"{ticker} 無法載入")
                    continue

                with st.container(border=True):
                    st.markdown(f"##### {info['label']}")
                    price_str = format_price(info["price"], False)
                    delta_str = f"{info['change']:+.2f}  ({info['change_pct']:+.2f}%)"
                    st.metric(label="", value=price_str, delta=delta_str, label_visibility="collapsed")

                    if info.get("week_52_high") and info.get("week_52_low"):
                        lo = format_price_md(info["week_52_low"], False)
                        hi = format_price_md(info["week_52_high"], False)
                        st.caption(f"52週  {lo} – {hi}")
                    if info.get("pe_ratio"):
                        st.caption(f"P/E {info['pe_ratio']:.1f}　成交量 {format_volume(info['volume'])}")

                    b1, b2, b3, b4 = st.columns(4)
                    with b1:
                        if st.button("💼 持有", key=f"us_hold_{ticker}_{grp}", use_container_width=True):
                            portfolio["us_groups"].setdefault("持有", [])
                            add_to_group(portfolio, ticker, "持有", "us")
                            save_portfolio(portfolio)
                            st.toast(f"{ticker} 已加入「持有」群組")
                    with b2:
                        if st.button("📌 自選", key=f"us_watch_{ticker}_{grp}", use_container_width=True):
                            portfolio["us_groups"].setdefault("自選", [])
                            add_to_group(portfolio, ticker, "自選", "us")
                            save_portfolio(portfolio)
                            st.toast(f"{ticker} 已加入「自選」")
                    with b3:
                        if st.button("🏠 首頁", key=f"us_home_{ticker}_{grp}", use_container_width=True):
                            if add_to_home_watch(portfolio, ticker):
                                save_portfolio(portfolio)
                                st.toast(f"{ticker} 已加入首頁追蹤")
                            else:
                                st.toast("已在首頁追蹤中")
                    with b4:
                        if st.button("✕", key=f"us_rm_{ticker}_{grp}", use_container_width=True, type="secondary"):
                            remove_from_group(portfolio, ticker, grp, "us")
                            save_portfolio(portfolio)
                            st.rerun()
