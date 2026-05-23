from __future__ import annotations

import re
from itertools import zip_longest
import streamlit as st

from utils.portfolio import (
    load_portfolio, save_portfolio, remove_from_home_watch,
    get_profile_name, get_profile_pin_hash, verify_pin, get_profile_holdings,
)
from utils.stock_data import (
    get_stock_info, format_price, format_volume, get_market_movers,
    get_sector_performance, find_sectors_for_ticker,
    get_usd_twd_rate, get_usd_twd_rate_detail, TW_NAMES_REVERSE,
)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
portfolio = st.session_state.portfolio
settings = portfolio.get("settings", {})

# ── Query-param navigation (from stock hyperlinks on this page) ───────────────
if "detail" in st.query_params:
    st.session_state.detail_ticker = st.query_params["detail"]
    st.query_params.clear()
    st.switch_page("pages/7_個股詳細資訊.py")

dashboard_name = settings.get("dashboard_name", "股票 Dashboard")
st.header(f"📈 {dashboard_name}")
st.caption("台股 / 美股 追蹤 · K線圖 · 持倉管理")

# ── Helpers ───────────────────────────────────────────────────────────────────

def is_tw(ticker: str) -> bool:
    if ticker.endswith(".TW") or ticker.endswith(".TWO"):
        return True
    if re.match(r"^\d+[A-Z]?$", ticker):
        return True
    if any("一" <= c <= "鿿" for c in ticker):
        return True
    return False


def resolve_price(ticker: str) -> dict | None:
    info = get_stock_info(ticker)
    if info:
        return info
    if any("一" <= c <= "鿿" for c in ticker):
        real = TW_NAMES_REVERSE.get(ticker)
        if real:
            return get_stock_info(real)
    # Bare numeric TW ticker (e.g. "3105") → try .TW then .TWO
    if is_tw(ticker) and not ticker.endswith(".TW") and not ticker.endswith(".TWO"):
        result = get_stock_info(ticker + ".TW")
        if result:
            return result
        return get_stock_info(ticker + ".TWO")
    # .TW failed (OTC-listed stock) → try .TWO
    if ticker.endswith(".TW"):
        return get_stock_info(ticker.replace(".TW", ".TWO"))
    return None


def _badge(text: str) -> str:
    return (
        "<span style='display:inline-block;"
        "background:rgba(77,171,245,0.12);"
        "border:1px solid rgba(77,171,245,0.30);"
        "padding:1px 9px;border-radius:10px;"
        "font-size:0.77em;color:#4dabf5;"
        "vertical-align:middle;font-weight:500'>"
        f"{text}</span>"
    )


def stock_card(info: dict, remove_key: str | None = None):
    tw = info["is_tw"]
    sign = "▲" if info["change"] >= 0 else "▼"
    price_str = format_price(info["price"], tw)
    mbs = find_sectors_for_ticker(info["ticker"])
    badge_html = (" " + _badge(mbs[0][1])) if mbs else ""

    with st.container(border=True):
        lbl = info["label"].replace("&", "&amp;")
        title_col, nav_col = st.columns([7, 3])
        with title_col:
            st.markdown(f"<strong>{lbl}</strong>{badge_html}", unsafe_allow_html=True)
        with nav_col:
            nav_key = f"card_nav_{info['ticker']}_{remove_key or 'x'}"
            if st.button("🔍 詳情", key=nav_key, use_container_width=True, type="secondary"):
                st.session_state.detail_ticker = info["ticker"]
                st.switch_page("pages/7_個股詳細資訊.py")

        col_p, col_d = st.columns([3, 2])
        with col_p:
            st.markdown(f"### {price_str}")
        with col_d:
            chg_clr = "#ff4b4b" if info["change"] >= 0 else "#21c55d"
            st.markdown(
                f"<span style='color:{chg_clr};font-size:1.1em;font-weight:600'>"
                f"{sign} {info['change_pct']:+.2f}%</span>",
                unsafe_allow_html=True,
            )
            st.caption(f"今日 {info['change']:+.2f}")

        if info.get("week_52_high") and info.get("week_52_low"):
            lo, hi, cur = info["week_52_low"], info["week_52_high"], info["price"]
            ratio = (cur - lo) / (hi - lo) if hi > lo else 0.5
            st.progress(float(min(max(ratio, 0.0), 1.0)))
            st.caption(
                f"52週  {format_price(lo, tw)} – {format_price(hi, tw)}"
            )

        meta = []
        if info.get("pe_ratio"):
            meta.append(f"P/E {info['pe_ratio']:.1f}")
        meta.append(f"量 {format_volume(info['volume'])}")
        if info.get("last_trade_date"):
            meta.append(f"截至 {info['last_trade_date']}")
        st.caption("　".join(meta))

        if remove_key:
            if st.button("✕ 移除", key=remove_key, use_container_width=True, type="secondary"):
                remove_from_home_watch(portfolio, info["ticker"])
                save_portfolio(portfolio)
                st.rerun()


# ── Section 1: Home watch ─────────────────────────────────────────────────────
home_watch: list[str] = portfolio.get("home_watch", [])

st.subheader("📌 首頁追蹤")

if not home_watch:
    st.info("尚未加入任何追蹤股票。請至「台股」或「美股」頁面，點擊「🏠 加入首頁」。")
else:
    tw_watch = [t for t in home_watch if is_tw(t)]
    us_watch = [t for t in home_watch if not is_tw(t)]

    col_tw, col_us = st.columns(2)
    with col_tw:
        st.markdown("**🇹🇼 台股**")
        if not tw_watch:
            st.caption("尚無台股")
        for ticker in tw_watch:
            info = resolve_price(ticker)
            if info:
                stock_card(info, remove_key=f"rm_home_{ticker}")
    with col_us:
        st.markdown("**🇺🇸 美股**")
        if not us_watch:
            st.caption("尚無美股")
        for ticker in us_watch:
            info = resolve_price(ticker)
            if info:
                stock_card(info, remove_key=f"rm_home_{ticker}")

st.divider()

# ── Section 2: Asset summary ──────────────────────────────────────────────────

profile_a_holdings = get_profile_holdings(portfolio, "profile_a")
profile_b_holdings = get_profile_holdings(portfolio, "profile_b")


def _home_profile_block(profile_id: str, profile_name: str, holdings: dict):
    """Render a PIN-gated summary block for one profile on the home page."""
    session_key = f"{profile_id}_unlocked"
    pin_hash = get_profile_pin_hash(portfolio, profile_id)

    if not holdings:
        st.caption("尚無持股紀錄")
        return

    # ── Locked ──────────────────────────────────────────────────────────────
    if pin_hash and not st.session_state.get(session_key):
        st.markdown(
            "<div style='"
            "  background:rgba(255,255,255,0.025);"
            "  border:1px solid rgba(255,255,255,0.07);"
            "  border-radius:12px;"
            "  text-align:center;"
            "  padding:28px 20px 20px;"
            "  margin-bottom:10px;"
            "'>"
            "  <div style='font-size:1.9em;margin-bottom:10px;opacity:0.6'>🔒</div>"
            "  <div style='font-size:0.82em;color:#777;letter-spacing:0.02em'>"
            "    持倉已鎖定"
            "  </div>"
            "</div>",
            unsafe_allow_html=True,
        )
        pin_val = st.text_input(
            "密碼",
            type="password",
            max_chars=4,
            key=f"home_{profile_id}_pin",
            label_visibility="collapsed",
            placeholder="輸入 4 位數字密碼",
        )
        st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
        if st.button(
            "解鎖",
            key=f"home_{profile_id}_unlock",
            type="primary",
            use_container_width=True,
        ):
            if pin_val and verify_pin(pin_val, pin_hash):
                st.session_state[session_key] = True
                st.rerun()
            else:
                st.error("密碼錯誤")
        return

    # ── Unlocked (or no PIN) ─────────────────────────────────────────────────
    if pin_hash:
        lock_col, _ = st.columns([2, 3])
        with lock_col:
            if st.button(
                "🔒 鎖定",
                key=f"home_{profile_id}_lock",
                type="secondary",
                use_container_width=True,
            ):
                st.session_state[session_key] = False
                st.rerun()

    # Fetch full info (prices + today's change)
    with st.spinner("載入報價…"):
        infos: dict[str, dict] = {}
        for t in holdings:
            inf = resolve_price(t)
            if inf:
                infos[t] = inf

    prices = {t: inf["price"] for t, inf in infos.items()}

    tw_h = {t: h for t, h in holdings.items() if is_tw(t)}
    us_h = {t: h for t, h in holdings.items() if not is_tw(t)}

    tw_cost    = sum(h["cost_per_share"] * h["quantity"] for h in tw_h.values())
    us_cost_usd = sum(h["cost_per_share"] * h["quantity"] for h in us_h.values())
    tw_mkt     = sum(prices.get(t, h["cost_per_share"]) * h["quantity"] for t, h in tw_h.items())
    us_mkt_usd = sum(prices.get(t, h["cost_per_share"]) * h["quantity"] for t, h in us_h.items())

    tw_today_twd = sum(
        infos[t].get("change", 0) * h["quantity"] for t, h in tw_h.items() if t in infos
    )
    us_today_usd = sum(
        infos[t].get("change", 0) * h["quantity"] for t, h in us_h.items() if t in infos
    )

    usd_twd, fx_date = get_usd_twd_rate_detail()
    combined_cost  = tw_cost + us_cost_usd * usd_twd
    combined_mkt   = tw_mkt + us_mkt_usd * usd_twd
    combined_pnl   = combined_mkt - combined_cost
    combined_pnl_pct = (combined_pnl / combined_cost * 100) if combined_cost else 0
    combined_today = tw_today_twd + us_today_usd * usd_twd

    tw_pnl     = tw_mkt - tw_cost
    tw_pnl_pct = (tw_pnl / tw_cost * 100) if tw_cost else 0
    us_pnl_usd = us_mkt_usd - us_cost_usd
    us_pnl_pct = (us_pnl_usd / us_cost_usd * 100) if us_cost_usd else 0

    # ── Metrics grid ──────────────────────────────────────────────────────────
    m1, m2 = st.columns(2)
    m1.metric("持倉市值", f"NT${combined_mkt:,.0f}")
    m2.metric("累計損益", f"NT${combined_pnl:+,.0f}", f"{combined_pnl_pct:+.2f}%")

    n1, n2 = st.columns(2)
    n1.metric("今日浮動", f"NT${combined_today:+,.0f}")
    n2.metric("持股", f"{len(infos)}/{len(holdings)} 支")

    if tw_h and us_h:
        t1, t2 = st.columns(2)
        t1.metric("🇹🇼 台股損益", f"NT${tw_pnl:+,.0f}", f"{tw_pnl_pct:+.2f}%")
        t2.metric("🇺🇸 美股損益", f"${us_pnl_usd:+,.2f}", f"{us_pnl_pct:+.2f}%")
    elif tw_h:
        st.metric("🇹🇼 台股損益", f"NT${tw_pnl:+,.0f}", f"{tw_pnl_pct:+.2f}%")
    elif us_h:
        st.metric("🇺🇸 美股損益", f"${us_pnl_usd:+,.2f}", f"{us_pnl_pct:+.2f}%")

    st.caption(
        f"匯率 1 USD = NT${usd_twd:.4f}　"
        f"來源：Yahoo Finance 銀行間即期（{fx_date}）"
    )

    if st.button(
        "📊 查看詳細持倉",
        key=f"home_{profile_id}_goto_detail",
        use_container_width=True,
    ):
        st.switch_page("pages/4_持倉管理.py")


if profile_a_holdings or profile_b_holdings:
    st.subheader("💰 持倉總覽")
    # Hide Streamlit "Press Enter to apply" hint and char counter
    st.markdown(
        """<style>[data-testid="InputInstructions"]{display:none!important}</style>""",
        unsafe_allow_html=True,
    )

    r_col, _ = st.columns([2, 8])
    with r_col:
        if st.button("🔄 刷新報價", key="refresh_assets"):
            st.cache_data.clear()
            st.rerun()

    name_a = get_profile_name(portfolio, "profile_a")
    name_b = get_profile_name(portfolio, "profile_b")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**👤 {name_a}**")
        _home_profile_block("profile_a", name_a, profile_a_holdings)
    with col_b:
        st.markdown(f"**👤 {name_b}**")
        _home_profile_block("profile_b", name_b, profile_b_holdings)

    st.divider()

# ── Section 3: Strong / weak ──────────────────────────────────────────────────
all_tracked_tickers = list({
    *home_watch,
    *profile_a_holdings.keys(),
    *profile_b_holdings.keys(),
})

if all_tracked_tickers:
    st.subheader("📊 強弱勢股（持倉 + 首頁追蹤）")

    ticker_infos = []
    with st.spinner(f"載入 {len(all_tracked_tickers)} 支股票報價…"):
        for ticker in all_tracked_tickers:
            info = resolve_price(ticker)
            if info:
                ticker_infos.append(info)

    if not ticker_infos:
        st.info("所有股票報價目前無法取得，請稍後再試或點上方「🔄 刷新報價」。")
    elif ticker_infos:
        ranked = sorted(ticker_infos, key=lambda x: x["change_pct"], reverse=True)
        n = min(10, len(ranked))
        gainers = ranked[:n]
        losers = ranked[-n:][::-1]

        def _gainer_loser_cell(info: dict, bull: bool) -> str:
            mbs = find_sectors_for_ticker(info["ticker"])
            badge_html = (" " + _badge(mbs[0][1])) if mbs else ""
            clr = "#ff4b4b" if bull else "#21c55d"
            sign = "▲" if bull else "▼"
            pct = info["change_pct"] if bull else abs(info["change_pct"])
            flag = "🇹🇼 " if info.get("is_tw") else "🇺🇸 "
            lbl = info["label"].replace("&", "&amp;")
            ticker = info["ticker"]
            price = format_price(info["price"], info["is_tw"])
            return (
                f"<div style='font-weight:600;line-height:1.4'>"
                f"<a href='?detail={ticker}' style='color:inherit;text-decoration:none'>"
                f"<span style='font-size:0.85em'>{flag}</span>{lbl}</a>"
                f"{badge_html}</div>"
                f"<div style='font-size:0.85em;margin-top:2px'>"
                f"<span style='color:{clr};font-weight:600'>{sign} {pct:.2f}%</span>"
                f"&nbsp;&nbsp;{price}</div>"
            )

        cell_l = "padding:5px 16px 5px 0"
        cell_r = "padding:5px 0 5px 16px"
        items_html = "".join(
            f"<div style='{cell_l}'>{_gainer_loser_cell(g, True) if g else ''}</div>"
            f"<div style='{cell_r}'>{_gainer_loser_cell(l, False) if l else ''}</div>"
            for g, l in zip_longest(gainers, losers)
        )
        hdr = "font-size:0.88em;font-weight:600;padding-bottom:8px"
        st.markdown(
            f"<div style='display:grid;grid-template-columns:1fr 1fr'>"
            f"<div style='{hdr};padding-right:16px'>🔴 強勢股（今日漲幅前{n}）</div>"
            f"<div style='{hdr};padding-left:16px'>🟢 弱勢股（今日跌幅前{n}）</div>"
            f"{items_html}"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

# ── Section 4: Hot stocks recommendation ─────────────────────────────────────
st.subheader("🔥 台美股熱點推薦")
st.caption("從大盤常見股票池中，挑出今日漲跌幅前 5 名")

if "hot_loaded" not in st.session_state:
    st.session_state.hot_loaded = False

if not st.session_state.hot_loaded:
    if st.button("🔍 載入今日熱點（需約 20–30 秒）", type="primary"):
        st.session_state.hot_loaded = True
        st.rerun()
else:
    r2_col, _ = st.columns([2, 6])
    with r2_col:
        if st.button("🔄 重新整理熱點"):
            st.cache_data.clear()
            st.session_state.hot_loaded = True
            st.rerun()

    def _sector_block(sectors: list[dict], is_tw_market: bool):
        for row_start in range(0, len(sectors), 2):
            row = sectors[row_start : row_start + 2]
            cols = st.columns(2)
            for col, s in zip(cols, row):
                avg = s["avg_change_pct"]
                clr = "#ff4b4b" if avg >= 0 else "#21c55d"
                sign = "▲" if avg >= 0 else "▼"
                with col:
                    with st.container(border=True):
                        head_col, pct_col = st.columns([5, 2])
                        with head_col:
                            st.markdown(
                                f"<span style='font-size:0.95em;font-weight:700'>"
                                f"{s['icon']} {s['name']}</span>"
                                f"<br><small style='color:#888'>{s['desc']}</small>",
                                unsafe_allow_html=True,
                            )
                        with pct_col:
                            st.markdown(
                                f"<div style='text-align:right;font-size:1.1em;"
                                f"font-weight:700;color:{clr};padding-top:4px'>"
                                f"{sign} {abs(avg):.2f}%</div>",
                                unsafe_allow_html=True,
                            )
                        top3 = s["stocks"][:3]
                        if top3:
                            chips = []
                            for si in top3:
                                sc = "#ff4b4b" if si["change_pct"] >= 0 else "#21c55d"
                                arrow = "▲" if si["change_pct"] >= 0 else "▼"
                                nm = si["display_name"] if is_tw_market else si["ticker"]
                                chips.append(
                                    f"<span style='display:inline-block;"
                                    f"background:rgba(255,255,255,0.06);border-radius:6px;"
                                    f"padding:2px 6px;margin:1px 2px 1px 0;font-size:0.78em;"
                                    f"color:{sc}'>{nm}&nbsp;{arrow}{abs(si['change_pct']):.1f}%</span>"
                                )
                            st.markdown(" ".join(chips), unsafe_allow_html=True)

    def _hot_stock_cell(info: dict, bull: bool) -> str:
        mbs = find_sectors_for_ticker(info["ticker"])
        badge_html = (" " + _badge(mbs[0][1])) if mbs else ""
        clr = "#ff4b4b" if bull else "#21c55d"
        sign = "▲" if bull else "▼"
        pct = abs(info["change_pct"])
        lbl = info["label"].replace("&", "&amp;")
        ticker = info["ticker"]
        price = format_price(info["price"], info["is_tw"])
        return (
            f"<div style='font-weight:600;line-height:1.4'>"
            f"<a href='?detail={ticker}' style='color:inherit;text-decoration:none'>{lbl}</a>"
            f"{badge_html}</div>"
            f"<div style='font-size:0.85em;margin-top:2px'>"
            f"<span style='color:{clr};font-weight:600'>{sign} {pct:.2f}%</span>"
            f"&nbsp;&nbsp;{price}</div>"
        )

    def _pair_movers_grid(gainers: list[dict], losers: list[dict]):
        cell_l = "padding:5px 16px 5px 0"
        cell_r = "padding:5px 0 5px 16px"
        items = "".join(
            f"<div style='{cell_l}'>{_hot_stock_cell(g, True) if g else ''}</div>"
            f"<div style='{cell_r}'>{_hot_stock_cell(l, False) if l else ''}</div>"
            for g, l in zip_longest(gainers, losers)
        )
        hdr = "font-size:0.88em;font-weight:600;padding-bottom:8px"
        st.markdown(
            f"<div style='display:grid;grid-template-columns:1fr 1fr'>"
            f"<div style='{hdr};padding-right:16px'>🔴 強勢</div>"
            f"<div style='{hdr};padding-left:16px'>🟢 弱勢</div>"
            f"{items}"
            f"</div>",
            unsafe_allow_html=True,
        )

    hot_tab_tw, hot_tab_us = st.tabs(["🇹🇼 台股熱點", "🇺🇸 美股熱點"])

    with hot_tab_tw:
        st.markdown("**🏭 族群排行**")
        with st.spinner("計算族群…"):
            tw_sectors = get_sector_performance("tw")
        _sector_block(tw_sectors, is_tw_market=True)
        st.divider()
        st.markdown("**📈 個股排行 Top 10**")
        with st.spinner("載入個股…"):
            tw_gainers, tw_losers = get_market_movers("tw", top_n=10)
        _pair_movers_grid(tw_gainers, tw_losers)

    with hot_tab_us:
        st.markdown("**🏭 族群排行**")
        with st.spinner("計算族群…"):
            us_sectors = get_sector_performance("us")
        _sector_block(us_sectors, is_tw_market=False)
        st.divider()
        st.markdown("**📈 個股排行 Top 10**")
        with st.spinner("載入個股…"):
            us_gainers, us_losers = get_market_movers("us", top_n=10)
        _pair_movers_grid(us_gainers, us_losers)
