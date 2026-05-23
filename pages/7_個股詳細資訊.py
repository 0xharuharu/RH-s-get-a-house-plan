from __future__ import annotations

import re
import datetime
import streamlit as st

from utils.portfolio import load_portfolio, save_portfolio, add_to_group, add_to_home_watch
from utils.stock_data import (
    get_stock_detail, get_historical_data, get_stock_info,
    get_news_rss, get_news_alpha_vantage, get_news_finnhub,
    get_news_cnyes, get_news_tw_multi,
    translate_to_zh,
    find_sectors_for_ticker, YFINANCE_TO_SECTOR,
    TW_SECTOR_GROUPS, US_SECTOR_GROUPS,
    TW_NAMES, TW_NAMES_REVERSE,
    _TW_NEWS_DOMAINS,
)
from utils.charts import create_candlestick_chart

st.set_page_config(page_title="個股詳細資訊", page_icon="🔍", layout="wide")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
portfolio = st.session_state.portfolio


# ── Helpers ───────────────────────────────────────────────────────────────────

def resolve_query(query: str) -> str | None:
    q = query.strip()
    if not q:
        return None
    if any("一" <= c <= "鿿" for c in q):
        return TW_NAMES_REVERSE.get(q)
    if "." in q or "^" in q:
        return q.upper()
    if re.match(r"^\d+[A-Z]?$", q):
        return q + ".TW"
    return q.upper()


def fmt_val(val: float | None, dec: int = 2) -> str:
    return "—" if val is None else f"{val:,.{dec}f}"


def fmt_pct(val: float | None) -> str:
    return "—" if val is None else f"{val * 100:.1f}%"


def fmt_large(val: float | None) -> str:
    if val is None:
        return "—"
    if val >= 1e12:
        return f"{val / 1e12:.2f}T"
    if val >= 1e9:
        return f"{val / 1e9:.2f}B"
    if val >= 1e6:
        return f"{val / 1e6:.2f}M"
    return f"{val:,.0f}"


def rec_text(val: float) -> str:
    if val <= 1.5: return "強力買進 ★★★"
    if val <= 2.5: return "買進 ★★"
    if val <= 3.5: return "持有 ★"
    if val <= 4.5: return "賣出"
    return "強力賣出"


# ── Search bar ────────────────────────────────────────────────────────────────
st.header("🔍 個股詳細資訊")

col_q, col_btn = st.columns([5, 1])
with col_q:
    query = st.text_input(
        "搜尋",
        placeholder="代號或中文名稱，例：2330　台積電　AAPL　00981A",
        label_visibility="collapsed",
    )
with col_btn:
    search_btn = st.button("搜尋", type="primary", use_container_width=True)

if "detail_ticker" not in st.session_state:
    st.session_state.detail_ticker = ""

if search_btn and query:
    resolved = resolve_query(query)
    if resolved:
        st.session_state.detail_ticker = resolved
    else:
        st.warning("找不到對應股票，請確認名稱或代號")

ticker = st.session_state.detail_ticker
if not ticker:
    st.info("輸入股票代號或中文名稱後按搜尋。支援台股（2330 / 台積電）、美股（AAPL）、ETF（0050）。")
    st.stop()

# ── Fetch data ────────────────────────────────────────────────────────────────
with st.spinner(f"載入 {ticker} 資料…"):
    detail = get_stock_detail(ticker)
    if not detail and ticker.endswith(".TW"):
        alt = ticker.replace(".TW", ".TWO")
        detail = get_stock_detail(alt)
        if detail:
            ticker = alt

if not detail:
    st.error(f"無法取得 **{ticker}** 的資料，請確認代號是否正確（台股可嘗試加 .TW）。")
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────
is_tw = detail["is_tw"]
currency = detail["currency"]
chg = detail["change"]
chg_pct = detail["change_pct"]
sign = "▲" if chg >= 0 else "▼"
color = "red" if chg >= 0 else "green"

disp = detail["display_name"]
st.markdown(f"## {disp}　`{ticker}`")

sec_parts = [detail.get("sector", ""), detail.get("industry", "")]
sec_line = " › ".join(p for p in sec_parts if p)
if sec_line:
    st.caption(sec_line)

h1, h2, h3, h4 = st.columns(4)
h1.metric("現價", f"{currency} {detail['price']:,.2f}", f"{sign} {chg_pct:+.2f}%")
h2.metric("今日漲跌", f"{chg:+.2f}")
if detail.get("week_52_high"):
    h3.metric("52週高", f"{detail['week_52_high']:,.2f}")
    h4.metric("52週低", f"{detail['week_52_low']:,.2f}")

if detail.get("last_trade_date"):
    st.caption(f"📅 報價截至 {detail['last_trade_date']}（以yfinance最新交易日收盤價計算）")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_chart, tab_fund, tab_sector, tab_news, tab_add = st.tabs(
    ["📊 行情圖", "📋 基本面", "🏭 產業族群", "📰 新聞", "➕ 加入觀察"]
)

# ── 行情圖 ────────────────────────────────────────────────────────────────────
with tab_chart:
    period_map = {"1個月": "1mo", "3個月": "3mo", "6個月": "6mo", "1年": "1y", "2年": "2y"}
    cp1, cp2, _ = st.columns([2, 4, 4])
    with cp1:
        period_label = st.selectbox("期間", list(period_map.keys()), index=1, key="dt_period")
    with cp2:
        mas = st.multiselect("均線", [5, 10, 20, 60, 200], default=[5, 20], key="dt_mas")

    with st.spinner("載入K線…"):
        df = get_historical_data(ticker, period_map[period_label])

    if df.empty:
        st.warning("無法取得歷史資料")
    else:
        fig = create_candlestick_chart(df, ticker, detail["label"], mas)
        st.plotly_chart(fig, use_container_width=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("成交量", fmt_large(float(detail["volume"])))
    if detail.get("market_cap"):
        m2.metric("市值", fmt_large(detail["market_cap"]))
    if detail.get("pe_trailing"):
        m3.metric("P/E (TTM)", fmt_val(detail["pe_trailing"]))

# ── 基本面 ────────────────────────────────────────────────────────────────────
with tab_fund:
    st.markdown("#### 估值")
    f1, f2, f3 = st.columns(3)
    f1.metric("P/E (TTM)", fmt_val(detail.get("pe_trailing")))
    f2.metric("P/E (Forward)", fmt_val(detail.get("pe_forward")))
    f3.metric("P/B", fmt_val(detail.get("pb_ratio")))

    st.markdown("#### 獲利能力")
    g1, g2, g3 = st.columns(3)
    g1.metric("ROE", fmt_pct(detail.get("roe")))
    g2.metric("毛利率", fmt_pct(detail.get("gross_margin")))
    g3.metric("營業利益率", fmt_pct(detail.get("operating_margin")))

    st.markdown("#### 成長")
    gr1, gr2, gr3 = st.columns(3)
    gr1.metric("營收成長 YoY", fmt_pct(detail.get("revenue_growth")))
    gr2.metric("EPS成長 YoY", fmt_pct(detail.get("earnings_growth")))
    gr3.metric("總營收", fmt_large(detail.get("revenue")))

    st.markdown("#### 財務結構")
    d1, d2 = st.columns(2)
    d1.metric("ROA", fmt_pct(detail.get("roa")))
    d2.metric("負債比 (D/E)", fmt_val(detail.get("debt_equity")))

    rec = detail.get("recommendation")
    if rec is not None:
        st.markdown("#### 分析師評等")
        a1, a2, a3 = st.columns(3)
        a1.metric("共識評等", rec_text(rec))
        a2.metric("評分 (1=強買 5=強賣)", fmt_val(rec))
        if detail.get("target_price"):
            a3.metric("目標價", f"{detail['target_price']:,.2f}")
        if detail.get("analyst_count"):
            st.caption(f"共 {detail['analyst_count']} 位分析師")

    summary = detail.get("summary", "")
    if summary:
        st.markdown("#### 公司簡介")
        with st.expander("展開閱讀"):
            st.write(summary)

    if not any([
        detail.get("pe_trailing"), detail.get("pb_ratio"), detail.get("roe"),
        detail.get("revenue"), detail.get("recommendation"),
    ]):
        st.info("此股票的基本面資料目前無法從 yfinance 取得（台股ETF通常無此資料）。")

# ── 產業族群 ──────────────────────────────────────────────────────────────────
with tab_sector:
    yf_sector = detail.get("sector", "")
    yf_industry = detail.get("industry", "")
    if yf_sector:
        st.markdown(f"**Yahoo Finance 分類** — {yf_sector} › {yf_industry}")
        st.markdown("")

    def _render_sector_card(sector_name: str, meta: dict, highlight_ticker: str):
        with st.container(border=True):
            st.markdown(f"{meta['icon']} **{sector_name}** — {meta['desc']}")
            peers = [t for t in meta["tickers"] if t != highlight_ticker]
            peer_parts = []
            for p in peers[:6]:
                p_info = get_stock_info(p)
                if p_info:
                    sc = "red" if p_info["change_pct"] >= 0 else "green"
                    nm = p_info.get("display_name", p)
                    peer_parts.append(f":{sc}[{nm} {p_info['change_pct']:+.1f}%]")
                else:
                    peer_parts.append(p)
            if peer_parts:
                st.markdown("同族群：" + "　".join(peer_parts))

    memberships = find_sectors_for_ticker(ticker)

    if memberships:
        st.markdown("**所屬族群**")
        for _mkt, sector_name, meta in memberships:
            _render_sector_card(sector_name, meta, ticker)
    else:
        # Dynamic match via yfinance industry label
        dynamic_names: list[str] = YFINANCE_TO_SECTOR.get(yf_industry, [])
        dynamic_hits: list[tuple[str, dict]] = []
        for sname in dynamic_names:
            for grp in (TW_SECTOR_GROUPS, US_SECTOR_GROUPS):
                if sname in grp:
                    dynamic_hits.append((sname, grp[sname]))

        if dynamic_hits:
            st.markdown(
                f"此股票不在預設名單中，但依 Yahoo Finance 行業分類 "
                f"**{yf_industry}** 找到以下相關族群："
            )
            for sname, meta in dynamic_hits:
                _render_sector_card(sname, meta, ticker)
        else:
            st.info("此股票不在任何預設族群中，且 Yahoo Finance 行業分類無法對應。")

    with st.expander("查看所有定義族群"):
        groups_ref = TW_SECTOR_GROUPS if is_tw else US_SECTOR_GROUPS
        for sname, smeta in groups_ref.items():
            labels = []
            for t in smeta["tickers"]:
                cn = TW_NAMES.get(t)
                labels.append(cn if cn else t.replace(".TW", ""))
            st.markdown(f"**{smeta['icon']} {sname}** — {smeta['desc']}")
            st.caption("　".join(labels))

# ── 新聞 ──────────────────────────────────────────────────────────────────────
with tab_news:
    import collections

    def _render_news_cards(articles: list[dict], source_label: str):
        # Limit the displayed source list to avoid a super-long caption
        src_parts = source_label.split(" + ") if source_label else []
        if len(src_parts) > 5:
            displayed = "、".join(src_parts[:5]) + f" 等 {len(src_parts)} 個來源"
        else:
            displayed = "、".join(src_parts) if src_parts else "—"
        st.caption(f"資料來源：{displayed}")
        st.markdown("")

        # Group by date
        by_date: dict[str, list[dict]] = collections.defaultdict(list)
        no_date: list[dict] = []
        for art in articles:
            ts = art.get("time", 0)
            if ts:
                try:
                    date_key = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                    by_date[date_key].append(art)
                    continue
                except Exception:
                    pass
            no_date.append(art)

        for date_key in sorted(by_date.keys(), reverse=True):
            st.markdown(f"**📅 {date_key}**")
            for art in by_date[date_key]:
                _news_card(art)
            st.markdown("")

        if no_date:
            st.markdown("**📅 日期不明**")
            for art in no_date:
                _news_card(art)

    _SENTIMENT_STYLE = {
        "Bullish":          ("🟢 看漲", "#4caf50"),
        "Somewhat-Bullish": ("🟡 偏漲", "#8bc34a"),
        "Neutral":          ("⚪ 中性", "#9e9e9e"),
        "Somewhat-Bearish": ("🟠 偏跌", "#ff9800"),
        "Bearish":          ("🔴 看跌", "#f44336"),
    }

    _SOURCE_BADGE: dict[str, str] = {
        "鉅亨網":    "rgba(220,60,60,0.15)",
        "自由財經":  "rgba(0,150,80,0.15)",
        "經濟日報":  "rgba(0,100,200,0.15)",
        "CMoney":    "rgba(255,140,0,0.15)",
        "MoneyDJ":   "rgba(120,80,200,0.15)",
        "工商時報":  "rgba(180,80,0,0.15)",
        "中央社":    "rgba(80,140,160,0.15)",
        "科技新報":  "rgba(0,160,160,0.15)",
        "財訊":      "rgba(160,100,0,0.15)",
        "今周刊":    "rgba(0,120,100,0.15)",
        "財經媒體":  "rgba(100,100,100,0.12)",
        "Finnhub":       "rgba(0,180,120,0.15)",
        "Alpha Vantage": "rgba(80,140,230,0.15)",
        "yfinance":      "rgba(120,120,120,0.12)",
        "RSS":           "rgba(120,120,120,0.12)",
    }

    def _source_chip(platform: str) -> str:
        bg = _SOURCE_BADGE.get(platform, "rgba(100,100,100,0.12)")
        return (
            f"<span style='display:inline-block;background:{bg};"
            f"border-radius:8px;padding:1px 7px;font-size:0.73em;"
            f"vertical-align:middle;opacity:0.9'>{platform}</span>"
        )

    def _desc_is_dup(title: str, desc: str) -> bool:
        """True when description repeats the title (common in RSS feeds)."""
        if not desc:
            return True
        import re as _re
        clean = _re.sub(r"\s*[-–]\s*\S+\.\S+$", "", desc.strip())
        prefix = title[:min(30, len(title))]
        return clean.startswith(prefix) or clean.strip() == title.strip()

    def _news_card(art: dict):
        title = art.get("title", "（無標題）")
        publisher = art.get("publisher", "")
        platform = art.get("source_platform", "")
        link = art.get("link", "")
        ts = art.get("time", 0)
        desc = art.get("description", "")
        sentiment = art.get("sentiment", "")
        lang = art.get("lang", "")

        time_str = ""
        if ts:
            try:
                time_str = datetime.datetime.fromtimestamp(ts).strftime("%H:%M")
            except Exception:
                pass

        title_esc = title.replace("<", "&lt;").replace(">", "&gt;")
        title_html = (
            f"<a href='{link}' target='_blank' "
            f"style='color:inherit;text-decoration:none;font-weight:600;font-size:0.96em'>"
            f"{title_esc}</a>"
            if link else f"<strong style='font-size:0.96em'>{title_esc}</strong>"
        )

        sent_html = ""
        if sentiment and sentiment in _SENTIMENT_STYLE:
            icon_label, clr = _SENTIMENT_STYLE[sentiment]
            sent_html = (
                f"&nbsp;<span style='color:{clr};font-size:0.78em;vertical-align:middle'>"
                f"{icon_label}</span>"
            )

        chip = _source_chip(platform) if platform else ""
        meta_parts = []
        if publisher and publisher != platform:
            meta_parts.append(publisher)
        if time_str:
            meta_parts.append(time_str)
        meta_text = "　".join(meta_parts)

        # Show description only when it adds real content beyond the title
        show_desc = desc and not _desc_is_dup(title, desc)
        snippet_html = ""
        if show_desc:
            snippet = desc[:240].rstrip()
            if len(desc) > 240:
                snippet += "…"
            snippet_html = (
                f"<div style='color:#aaa;font-size:0.84em;"
                f"margin-top:4px;line-height:1.45'>{snippet}</div>"
            )

        st.markdown(
            f"<div style='padding:6px 0 4px'>"
            f"{title_html}{sent_html}"
            f"<div style='margin-top:3px'>"
            f"{chip}&nbsp;<span style='color:#888;font-size:0.79em'>{meta_text}</span>"
            f"</div>"
            f"{snippet_html}"
            f"</div>"
            f"<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);"
            f"margin:0 0 2px'>",
            unsafe_allow_html=True,
        )

        # Chinese translation (for English articles with real description)
        if lang == "en" and show_desc:
            with st.spinner("翻譯中…"):
                zh = translate_to_zh(desc[:300])
            if zh:
                st.markdown(
                    f"<div style='color:#7ecfff;font-size:0.83em;"
                    f"border-left:2px solid rgba(126,207,255,0.4);"
                    f"padding:3px 0 6px 10px;margin-bottom:6px'>📝 {zh}</div>"
                    f"<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);"
                    f"margin:0 0 2px'>",
                    unsafe_allow_html=True,
                )

    # ── Collect from all sources ───────────────────────────────────────────────
    api_keys = portfolio.get("api_keys", {})
    av_key  = api_keys.get("alpha_vantage", "")
    fh_key  = api_keys.get("finnhub", "")

    sources_used: list[str] = []
    all_news: list[dict] = []
    seen_prefixes: set[str] = set()  # deduplicate by first 40 chars

    def _merge(articles: list[dict], label: str | None = None):
        """Merge articles into all_news, deduplicating by title prefix.
        If label is None, each article's 'publisher' field is used as source_platform."""
        added: set[str] = set()
        for a in articles:
            t = a.get("title", "")
            if not t:
                continue
            prefix = t[:40].strip()
            if prefix in seen_prefixes:
                continue
            seen_prefixes.add(prefix)
            sp = label if label is not None else a.get("publisher", "財經媒體")
            all_news.append({**a, "source_platform": sp})
            added.add(sp)
        for sp in sorted(added):
            if sp not in sources_used:
                sources_used.append(sp)

    # 1. 鉅亨網 (TW only, no key)
    if is_tw:
        with st.spinner("鉅亨網新聞載入中…"):
            _merge(get_news_cnyes(ticker), "鉅亨網")

    # 1b. 多源台股財經（自由財經、經濟日報、CMoney、MoneyDJ、工商時報、中央社…）
    if is_tw:
        with st.spinner("台股多源財經新聞載入中…"):
            _merge(get_news_tw_multi(ticker))   # label=None → per-article publisher

    # 2. Finnhub (US only, needs key)
    if fh_key and not is_tw:
        with st.spinner("Finnhub 新聞載入中…"):
            _merge(get_news_finnhub(ticker, fh_key), "Finnhub")

    # 3. Alpha Vantage (US mainly, needs key)
    if av_key:
        with st.spinner("Alpha Vantage 新聞載入中…"):
            _merge(get_news_alpha_vantage(ticker, av_key), "Alpha Vantage")

    # 4. yfinance built-in
    _merge([a for a in detail.get("news", []) if a.get("title")], "yfinance")

    # 5. RSS fallback if still empty
    if not all_news:
        with st.spinner("嘗試 RSS 備援…"):
            _merge(get_news_rss(ticker), "RSS")

    if all_news:
        _render_news_cards(all_news, " + ".join(sources_used) if sources_used else "—")
    else:
        st.info(
            "目前無法取得任何新聞。\n\n"
            "- 🇹🇼 台股：[鉅亨網](https://news.cnyes.com/)　"
            "[奇摩股市](https://tw.finance.yahoo.com/)　[Moneydj](https://www.moneydj.com/)\n"
            "- 🇺🇸 美股：[Reuters](https://www.reuters.com/)　"
            "[CNBC](https://www.cnbc.com/)　[Seeking Alpha](https://seekingalpha.com/)"
        )
        if not (av_key or fh_key):
            st.caption("💡 前往「設定」→「新聞 API 金鑰」設定 Finnhub（美股）或 Alpha Vantage 免費 Key，可大幅提升新聞覆蓋率。")

# ── 加入觀察 ──────────────────────────────────────────────────────────────────
with tab_add:
    st.markdown("#### 加入觀察清單")
    market_key = "tw" if is_tw else "us"
    groups_key = f"{market_key}_groups"
    user_groups = portfolio.get(groups_key, {})
    group_names = list(user_groups.keys())

    memberships = find_sectors_for_ticker(ticker)
    if memberships:
        suggested = [m[1] for m in memberships]
        st.caption(f"依族群分類，建議加入：**{'、'.join(suggested)}**")

    if group_names:
        ac1, ac2 = st.columns([3, 2])
        with ac1:
            target_group = st.selectbox(
                "選擇群組", group_names, key="dt_target_grp",
            )
        with ac2:
            st.markdown("")
            if st.button("➕ 加入該群組", type="primary", use_container_width=True, key="dt_add_grp"):
                if add_to_group(portfolio, ticker, target_group, market_key):
                    save_portfolio(portfolio)
                    st.success(f"已將 {ticker} 加入「{target_group}」")
                else:
                    st.info("已在該群組中")
    else:
        st.info(f"尚無{'台股' if is_tw else '美股'}群組，請先至設定頁新增群組。")

    st.markdown("")
    if st.button("🏠 加入首頁追蹤", use_container_width=True, key="dt_add_home"):
        if add_to_home_watch(portfolio, ticker):
            save_portfolio(portfolio)
            st.success("已加入首頁追蹤")
        else:
            st.info("已在首頁追蹤中")
