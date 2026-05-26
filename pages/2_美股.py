from __future__ import annotations

import streamlit as st
from streamlit_sortables import sort_items
from utils.ai_analysis import fetch_ai_analysis
from utils.portfolio import (
    load_portfolio, save_portfolio,
    add_to_group, remove_from_group, add_to_home_watch,
    sync_holdings_to_groups,
)
from utils.stock_data import get_stock_info, format_price, format_price_md, format_volume, search_tickers

st.set_page_config(page_title="美股", page_icon="🇺🇸", layout="wide")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
portfolio = st.session_state.portfolio

# Auto-sync 持有 group with both profiles' holdings
if sync_holdings_to_groups(portfolio):
    save_portfolio(portfolio)

# ── Sidebar ───────────────────────────────────────────────────────────────────
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
        raw = st.text_input("代號或名稱", placeholder="例: NVDA 或 Nvidia", key="us_raw")
        tgt = st.selectbox("加入群組", groups, key="us_tgt")
        if st.button("搜尋 / 新增", key="us_btn_add",
                     use_container_width=True, type="primary"):
            query = raw.strip()
            if query and tgt:
                direct = query.upper()
                if get_stock_info(direct):
                    if add_to_group(portfolio, direct, tgt, "us"):
                        save_portfolio(portfolio)
                        st.session_state.pop("us_suggestions", None)
                        st.session_state.pop("us_add_msg", None)
                        st.rerun()
                    else:
                        st.session_state["us_add_msg"] = (
                            f"⚠ **{direct}** 已在群組「{tgt}」內"
                        )
                else:
                    with st.spinner("搜尋中…"):
                        suggs = search_tickers(query, max_results=6)
                    if suggs:
                        st.session_state["us_suggestions"]   = suggs
                        st.session_state["us_suggest_query"] = query
                        st.session_state["us_suggest_tgt"]   = tgt
                        st.session_state.pop("us_add_msg", None)
                    else:
                        st.session_state["us_add_msg"] = (
                            "找不到任何結果，請嘗試英文代號或完整公司名稱。"
                        )

        if st.session_state.get("us_add_msg"):
            st.warning(st.session_state["us_add_msg"])

        if st.session_state.get("us_suggestions"):
            suggs     = st.session_state["us_suggestions"]
            q_text    = st.session_state.get("us_suggest_query", "")
            saved_tgt = st.session_state.get("us_suggest_tgt", "")
            st.caption(f"「{q_text}」是否是指：")
            grp_tickers = portfolio.get("us_groups", {}).get(saved_tgt, [])
            for j, s in enumerate(suggs):
                already = s["symbol"] in grp_tickers
                lbl = f"{s['symbol']}  {s['name']}" + ("  ✓" if already else "")
                if st.button(lbl, key=f"us_sugg_{j}", use_container_width=True):
                    if already:
                        st.session_state["us_add_msg"] = (
                            f"⚠ **{s['symbol']}** 已在群組內"
                        )
                    else:
                        add_to_group(portfolio, s["symbol"], saved_tgt, "us")
                        save_portfolio(portfolio)
                        st.session_state.pop("us_suggestions", None)
                        st.session_state.pop("us_add_msg", None)
                        st.rerun()
            if st.button("取消", key="us_sugg_cancel",
                         use_container_width=True, type="secondary"):
                st.session_state.pop("us_suggestions", None)
                st.session_state.pop("us_add_msg", None)
                st.rerun()

    with st.expander("↕️ 群組排序"):
        st.caption("拖曳群組名稱以調整順序")
        groups_now = list(portfolio.get("us_groups", {}).keys())
        sorted_groups = sort_items(groups_now, direction="vertical", key="us_sort")
        if sorted_groups != groups_now:
            portfolio["us_groups"] = {k: portfolio["us_groups"][k] for k in sorted_groups}
            save_portfolio(portfolio)
            st.rerun()

    if st.button("🔄 重新整理報價", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
st.header("🇺🇸 美股")

group_names = list(portfolio.get("us_groups", {}).keys())
if not group_names:
    st.info("尚未建立任何群組，請從左側新增。")
    st.stop()

tabs = st.tabs(group_names)

COLS = 3   # cards per row


def render_us_card(ticker: str, grp: str):
    info = get_stock_info(ticker)
    if not info:
        with st.container(border=True):
            st.caption(f"⚠️ {ticker}")
            st.caption("無法載入報價")
            if st.button("✕", key=f"us_rm_err_{ticker}_{grp}",
                         type="secondary", use_container_width=True):
                remove_from_group(portfolio, ticker, grp, "us")
                save_portfolio(portfolio)
                st.rerun()
        return

    sign = "▲" if info["change"] >= 0 else "▼"
    clr  = "#ff4b4b" if info["change"] >= 0 else "#21c55d"
    price_str = format_price(info["price"], False)

    with st.container(border=True):
        # ── Compact price block ───────────────────────────────────────────
        st.markdown(
            f"<div style='margin-bottom:6px'>"
            f"<div class='stock-card-name'>{info['label']}</div>"
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
                f"　{format_price(lo, False)} – {format_price(hi, False)}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── 昨收 + Volume ──────────────────────────────────────────────────
        prev = info.get("prev_close")
        meta = []
        if prev is not None:
            meta.append(f"昨收 {format_price(prev, False)}")
        meta.append(f"量 {format_volume(info['volume'])}")
        st.markdown(
            f"<div class='stock-card-caption'>{'　'.join(meta)}</div>",
            unsafe_allow_html=True,
        )

        # ── Action buttons ────────────────────────────────────────────────
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button("🔍", key=f"us_det_{ticker}_{grp}",
                         use_container_width=True, help="查看個股"):
                st.session_state.detail_ticker = ticker
                st.switch_page("pages/7_個股詳細資訊.py")
        with b2:
            if st.button("💼", key=f"us_hold_{ticker}_{grp}",
                         use_container_width=True, help="加入持有"):
                portfolio["us_groups"].setdefault("持有", [])
                add_to_group(portfolio, ticker, "持有", "us")
                save_portfolio(portfolio)
                st.toast(f"{ticker} 已加入「持有」")
        with b3:
            if st.button("🏠", key=f"us_home_{ticker}_{grp}",
                         use_container_width=True, help="首頁追蹤"):
                if add_to_home_watch(portfolio, ticker):
                    save_portfolio(portfolio)
                    st.toast(f"{ticker} 已加入首頁追蹤")
                else:
                    st.toast("已在首頁追蹤中")
        with b4:
            if st.button("❌", key=f"us_rm_{ticker}_{grp}",
                         use_container_width=True, type="secondary", help="取消收藏"):
                remove_from_group(portfolio, ticker, grp, "us")
                save_portfolio(portfolio)
                st.rerun()

        # ── AI 買入分析 ───────────────────────────────────────────────────────
        ai_key = f"ai_us_{ticker}_{grp}"
        active  = st.session_state.get(ai_key, False)
        btn_lbl = "💡 收起分析" if active else "💡 買入分析"
        if st.button(btn_lbl, key=f"ai_btn_us_{ticker}_{grp}",
                     use_container_width=True):
            st.session_state[ai_key] = not active
            st.rerun()
        if st.session_state.get(ai_key):
            with st.spinner("AI 分析中…"):
                result = fetch_ai_analysis(ticker, info)
            import re as _re
            html_result = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', result)
            html_result = html_result.replace("\n", "<br>")
            st.markdown(
                "<div style='background:rgba(77,171,245,0.06);"
                "border:1px solid rgba(77,171,245,0.18);border-radius:8px;"
                "padding:12px 14px;margin-top:4px;font-size:0.86em;line-height:1.7'>"
                + html_result
                + "</div>",
                unsafe_allow_html=True,
            )


for tab, grp in zip(tabs, group_names):
    with tab:
        tickers = portfolio["us_groups"].get(grp, [])
        if not tickers:
            st.caption("此群組尚無股票。")
            continue

        for row_start in range(0, len(tickers), COLS):
            row = tickers[row_start : row_start + COLS]
            cols = st.columns(COLS)
            for i, ticker in enumerate(row):
                with cols[i]:
                    render_us_card(ticker, grp)
