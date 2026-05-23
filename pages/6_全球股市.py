from __future__ import annotations

import streamlit as st
from utils.portfolio import (
    load_portfolio, save_portfolio,
    get_global_watch, add_to_global_watch, remove_from_global_watch,
)
from utils.stock_data import get_stock_info, format_price, format_volume, INDEX_LABELS, search_tickers

st.set_page_config(page_title="全球股市", page_icon="🌍", layout="wide")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
portfolio = st.session_state.portfolio

# ── Index definitions ─────────────────────────────────────────────────────────
REGIONS: list[tuple[str, list[str]]] = [
    ("🌏 亞太", ["^TWII", "^N225", "^HSI", "^KS11", "^STI", "^AXJO"]),
    ("🌍 歐洲", ["^GDAXI", "^FTSE", "^FCHI", "^IBEX", "^SSMI"]),
    ("🌎 美洲", ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX"]),
]

EXTRA_LABELS: dict[str, str] = {
    "^KS11":  "韓國綜合指數",
    "^STI":   "新加坡海峽時報",
    "^AXJO":  "澳洲ASX 200",
    "^GDAXI": "德國DAX",
    "^FTSE":  "英國富時100",
    "^FCHI":  "法國CAC 40",
    "^IBEX":  "西班牙IBEX 35",
    "^SSMI":  "瑞士SMI",
    "^RUT":   "羅素2000",
}

ALL_LABELS = {**INDEX_LABELS, **EXTRA_LABELS}


def index_label(ticker: str) -> str:
    return ALL_LABELS.get(ticker, ticker)


def delta_color(chg_pct: float) -> str:
    return "🟢" if chg_pct >= 0 else "🔴"


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🌍 自選國際股")
    with st.expander("➕ 新增追蹤"):
        raw = st.text_input(
            "代號或名稱",
            placeholder="例：SIVE.ST / 700.HK / SK海力士",
            key="global_add_raw",
        )
        if st.button("搜尋 / 新增", key="global_btn_add", use_container_width=True,
                     type="primary"):
            query = raw.strip()
            if query:
                direct = query.upper()
                current_watch = portfolio.get("global_watch", [])
                # Exact ticker already in list?
                if direct in current_watch:
                    st.session_state["global_add_msg"] = (
                        f"⚠ **{direct}** 已在自選清單內"
                    )
                else:
                    # Try exact ticker first
                    test = get_stock_info(direct)
                    if test:
                        add_to_global_watch(portfolio, direct)
                        save_portfolio(portfolio)
                        st.session_state.pop("global_suggestions", None)
                        st.session_state.pop("global_add_msg", None)
                        st.rerun()
                    else:
                        # Search by name/keyword
                        with st.spinner("搜尋中…"):
                            suggestions = search_tickers(query, max_results=5)
                        if suggestions:
                            st.session_state["global_suggestions"] = suggestions
                            st.session_state["global_suggest_query"] = query
                            st.session_state.pop("global_add_msg", None)
                        else:
                            st.session_state["global_add_msg"] = (
                                "找不到任何結果，請嘗試輸入英文代號或名稱。"
                            )

        # Persistent message (duplicate / not-found)
        if st.session_state.get("global_add_msg"):
            st.warning(st.session_state["global_add_msg"])

        # Show suggestions if available
        if st.session_state.get("global_suggestions"):
            suggs = st.session_state["global_suggestions"]
            q_text = st.session_state.get("global_suggest_query", "")
            st.caption(f"「{q_text}」是否是指：")
            current_watch = portfolio.get("global_watch", [])
            for j, s in enumerate(suggs):
                already = s["symbol"] in current_watch
                btn_lbl = f"{s['symbol']}  {s['name']}"
                if already:
                    btn_lbl += "  ✓"
                if st.button(btn_lbl, key=f"gsugg_{j}", use_container_width=True):
                    if already:
                        st.session_state["global_add_msg"] = (
                            f"⚠ **{s['symbol']}** 已在自選清單內"
                        )
                    else:
                        add_to_global_watch(portfolio, s["symbol"])
                        save_portfolio(portfolio)
                        st.session_state.pop("global_suggestions", None)
                        st.session_state.pop("global_add_msg", None)
                        st.rerun()
            if st.button("取消", key="gsugg_cancel", use_container_width=True,
                         type="secondary"):
                st.session_state.pop("global_suggestions", None)
                st.session_state.pop("global_add_msg", None)
                st.rerun()

    if st.button("🔄 重新整理報價", use_container_width=True, key="global_refresh"):
        st.cache_data.clear()
        st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
st.title("🌍 全球股市")

# ── Market indices by region ──────────────────────────────────────────────────
st.subheader("📊 全球主要指數")

for region_name, tickers in REGIONS:
    st.markdown(f"**{region_name}**")
    cols = st.columns(len(tickers))
    for col, ticker in zip(cols, tickers):
        with col:
            with st.spinner(""):
                info = get_stock_info(ticker)
            if not info:
                st.metric(label=index_label(ticker), value="—")
                continue
            chg_pct = info["change_pct"]
            indicator = delta_color(chg_pct)
            label_text = f"{indicator} {index_label(ticker)}"
            price_val = f"{info['price']:,.2f}"
            delta_val = f"{info['change']:+.2f} ({chg_pct:+.2f}%)"
            st.metric(label=label_text, value=price_val, delta=delta_val)
    st.markdown("")

st.divider()

# ── International stock watchlist ─────────────────────────────────────────────
st.subheader("📌 自選國際股追蹤")

watch = get_global_watch(portfolio)

if not watch:
    st.info("尚無追蹤股票，請從左側新增（支援任意市場，例如 SIVE.ST、700.HK、BMW.DE）。")
else:
    n_cols = min(len(watch), 4)
    cols = st.columns(n_cols)
    # Deduplicate watch list in case replacements created duplicates
    seen_tickers: set[str] = set()
    deduped_watch: list[str] = []
    for t in watch:
        if t not in seen_tickers:
            seen_tickers.add(t)
            deduped_watch.append(t)
    if len(deduped_watch) != len(watch):
        portfolio["global_watch"] = deduped_watch
        save_portfolio(portfolio)
        watch = deduped_watch

    for i, ticker in enumerate(watch):
        with cols[i % n_cols]:
            with st.spinner(""):
                info = get_stock_info(ticker)
            with st.container(border=True):
                if not info:
                    st.markdown(
                        f"<strong>{ticker}</strong><br>"
                        f"<small style='color:#f08'>⚠ 無法取得資料</small>",
                        unsafe_allow_html=True,
                    )
                    # Offer search suggestions so the user can fix the ticker
                    sugg_key = f"card_sugg_{ticker}"
                    if sugg_key not in st.session_state:
                        st.session_state[sugg_key] = None
                    if st.session_state[sugg_key] is None:
                        if st.button("🔍 搜尋建議", key=f"global_suggest_btn_{i}",
                                     use_container_width=True, type="secondary"):
                            with st.spinner("搜尋中…"):
                                st.session_state[sugg_key] = search_tickers(
                                    ticker.split(".")[0], max_results=4
                                )
                            st.rerun()
                    else:
                        suggs = st.session_state[sugg_key]
                        if suggs:
                            st.caption("是否是指：")
                            current_wl = portfolio.get("global_watch", [])
                            for si, s in enumerate(suggs[:3]):
                                already_in = s["symbol"] in current_wl
                                btn_lbl = f"{s['symbol']}  {s['name']}"
                                if already_in:
                                    btn_lbl += "  ✓"
                                if st.button(
                                    btn_lbl,
                                    key=f"card_pick_{i}_{si}",
                                    use_container_width=True,
                                ):
                                    wl = portfolio.get("global_watch", [])
                                    new_sym = s["symbol"]
                                    if new_sym in wl:
                                        # New ticker already present → just remove the bad entry
                                        # and show a message
                                        wl = [t for t in wl if t != ticker]
                                        portfolio["global_watch"] = wl
                                        save_portfolio(portfolio)
                                        st.session_state.pop(sugg_key, None)
                                        st.session_state["global_add_msg"] = (
                                            f"⚠ **{new_sym}** 已在清單內，已移除無效代號 {ticker}"
                                        )
                                        st.rerun()
                                    else:
                                        wl = [new_sym if t == ticker else t for t in wl]
                                        portfolio["global_watch"] = wl
                                        save_portfolio(portfolio)
                                        st.session_state.pop(sugg_key, None)
                                        st.rerun()
                        else:
                            st.caption("找不到建議，請手動確認代號。")
                    if st.button("✕ 移除", key=f"global_rm_{i}", type="secondary",
                                 use_container_width=True):
                        remove_from_global_watch(portfolio, ticker)
                        save_portfolio(portfolio)
                        st.rerun()
                    continue

                is_tw = info.get("is_tw", False)
                display = info.get("display_name") or info.get("name", ticker)
                price_str = format_price(info["price"], is_tw)
                chg_clr = "#ff4b4b" if info["change"] >= 0 else "#21c55d"
                sign = "▲" if info["change"] >= 0 else "▼"

                lo = info.get("week_52_low")
                hi = info.get("week_52_high")
                curr = info.get("currency", "")
                w52 = f"52週 {curr} {lo:,.2f}–{hi:,.2f}" if lo and hi else "52週 —"
                pe_vol = []
                if info.get("pe_ratio"):
                    pe_vol.append(f"P/E {info['pe_ratio']:.1f}")
                pe_vol.append(f"量 {format_volume(info['volume'])}")
                date_str = (f"截至 {info['last_trade_date']}"
                            if info.get("last_trade_date") else "")

                st.markdown(
                    f"<div style='line-height:1.55'>"
                    f"<strong style='font-size:1.0em'>{display}</strong>"
                    f"<small style='color:#888;margin-left:6px'>{ticker}</small><br>"
                    f"<span style='font-size:1.35em;font-weight:700'>{price_str}</span>"
                    f"<span style='color:{chg_clr};font-weight:600;margin-left:8px'>"
                    f"{sign} {info['change_pct']:+.2f}%</span>"
                    f"<span style='color:#aaa;font-size:0.88em;margin-left:6px'>"
                    f"今日 {info['change']:+.2f}</span><br>"
                    f"<small style='color:#888'>{w52}</small><br>"
                    f"<small style='color:#888'>"
                    f"{'　'.join(pe_vol)}"
                    f"{'　' + date_str if date_str else ''}</small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                if st.button("✕", key=f"global_rm_{i}", type="secondary",
                             use_container_width=True):
                    remove_from_global_watch(portfolio, ticker)
                    save_portfolio(portfolio)
                    st.rerun()
