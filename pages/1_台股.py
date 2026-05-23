from __future__ import annotations

import streamlit as st
from utils.portfolio import load_portfolio, save_portfolio, add_to_group, remove_from_group, add_to_home_watch
from utils.stock_data import get_stock_info, format_price, format_price_md, format_volume

st.set_page_config(page_title="台股", page_icon="🇹🇼", layout="wide")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
portfolio = st.session_state.portfolio

# ── Sidebar ──────────────────────────────────────────────────────────────────
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

    if st.button("🔄 重新整理報價", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Main ─────────────────────────────────────────────────────────────────────
st.title("🇹🇼 台股")

group_names = list(portfolio.get("tw_groups", {}).keys())
if not group_names:
    st.info("尚未建立任何群組，請從左側新增。")
    st.stop()

tabs = st.tabs(group_names)

for tab, grp in zip(tabs, group_names):
    with tab:
        tickers = portfolio["tw_groups"].get(grp, [])
        if not tickers:
            st.caption("此群組尚無股票。")
            continue

        n = min(len(tickers), 4)
        cols = st.columns(n)

        for i, ticker in enumerate(tickers):
            with cols[i % n]:
                info = get_stock_info(ticker)
                # OTC fallback: 3105.TW → 3105.TWO
                actual_ticker = ticker
                if not info and ticker.endswith(".TW"):
                    alt = ticker.replace(".TW", ".TWO")
                    info = get_stock_info(alt)
                    if info:
                        actual_ticker = alt
                if not info:
                    with st.container(border=True):
                        st.error(f"{ticker} 無法載入")
                        st.caption("可能為上櫃股票（.TWO），或代號有誤")
                        if st.button("✕ 從群組移除", key=f"tw_rm_err_{ticker}_{grp}",
                                     type="secondary", use_container_width=True):
                            remove_from_group(portfolio, ticker, grp, "tw")
                            save_portfolio(portfolio)
                            st.rerun()
                    continue

                # Price card
                with st.container(border=True):
                    st.markdown(f"##### {info['label']}")
                    price_str = format_price(info["price"], True)
                    delta_str = f"{info['change']:+.2f}  ({info['change_pct']:+.2f}%)"
                    st.metric(label="", value=price_str, delta=delta_str, label_visibility="collapsed")

                    if info.get("week_52_high") and info.get("week_52_low"):
                        lo = format_price_md(info["week_52_low"], True)
                        hi = format_price_md(info["week_52_high"], True)
                        st.caption(f"52週  {lo} – {hi}")
                    meta2 = []
                    if info.get("pe_ratio"):
                        meta2.append(f"P/E {info['pe_ratio']:.1f}")
                    meta2.append(f"成交量 {format_volume(info['volume'])}")
                    if info.get("last_trade_date"):
                        meta2.append(f"截至 {info['last_trade_date']}")
                    st.caption("　".join(meta2))

                    # Action buttons
                    b1, b2, b3, b4 = st.columns(4)
                    with b1:
                        if st.button("💼 持有", key=f"tw_hold_{ticker}_{grp}", use_container_width=True):
                            portfolio["tw_groups"].setdefault("持有", [])
                            add_to_group(portfolio, ticker, "持有", "tw")
                            save_portfolio(portfolio)
                            st.toast(f"{info['display_name']} 已加入「持有」群組")
                    with b2:
                        if st.button("📌 自選", key=f"tw_watch_{ticker}_{grp}", use_container_width=True):
                            portfolio["tw_groups"].setdefault("自選", [])
                            add_to_group(portfolio, ticker, "自選", "tw")
                            save_portfolio(portfolio)
                            st.toast(f"{info['display_name']} 已加入「自選」")
                    with b3:
                        if st.button("🏠 首頁", key=f"tw_home_{ticker}_{grp}", use_container_width=True):
                            if add_to_home_watch(portfolio, ticker):
                                save_portfolio(portfolio)
                                st.toast(f"{info['display_name']} 已加入首頁追蹤")
                            else:
                                st.toast("已在首頁追蹤中")
                    with b4:
                        if st.button("✕", key=f"tw_rm_{ticker}_{grp}", use_container_width=True, type="secondary"):
                            remove_from_group(portfolio, ticker, grp, "tw")
                            save_portfolio(portfolio)
                            st.rerun()
