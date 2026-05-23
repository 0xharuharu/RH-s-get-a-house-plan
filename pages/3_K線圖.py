from __future__ import annotations

import streamlit as st
from utils.portfolio import load_portfolio, all_tickers
from utils.stock_data import (
    get_stock_info, get_historical_data, format_price, INDEX_LABELS,
)
from utils.charts import create_candlestick_chart, create_line_chart

st.set_page_config(page_title="K線圖", page_icon="📈", layout="wide")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
portfolio = st.session_state.portfolio

st.header("📈 K線圖")

# ── Ticker list：大盤指數永遠在最前面 ────────────────────────────────────────────
INDEX_TICKERS = ["^TWII", "^GSPC", "^DJI", "^IXIC"]
tw_tickers = all_tickers(portfolio, "tw")
us_tickers = all_tickers(portfolio, "us")
tracked = [t for t in (tw_tickers + us_tickers) if t not in INDEX_TICKERS]
all_options = INDEX_TICKERS + tracked


def ticker_display(t: str) -> str:
    if t in INDEX_LABELS:
        return INDEX_LABELS[t]
    info = get_stock_info(t)
    return info["label"] if info else t


# ── Controls ─────────────────────────────────────────────────────────────────
col_sel, col_period, col_type = st.columns([3, 2, 2])

with col_sel:
    selected = st.selectbox("選擇股票 / 指數", all_options, format_func=ticker_display)

with col_period:
    period = st.selectbox(
        "時間範圍",
        ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
        index=1,
        format_func=lambda x: {
            "1mo": "1 個月", "3mo": "3 個月", "6mo": "6 個月",
            "1y": "1 年", "2y": "2 年", "5y": "5 年",
        }[x],
    )

with col_type:
    chart_type = st.radio("圖表", ["K線圖", "走勢圖"], horizontal=True)

# ── MA selector ───────────────────────────────────────────────────────────────
st.markdown("**均線 MA**")
ma_cols = st.columns(6)
ma_options = [5, 10, 20, 30, 60, 200]
ma_defaults = [True, True, True, True, False, False]
selected_mas = []
for col, ma, default in zip(ma_cols, ma_options, ma_defaults):
    with col:
        if st.checkbox(f"MA{ma}", value=default, key=f"ma_{ma}"):
            selected_mas.append(ma)

st.divider()

# ── Chart ─────────────────────────────────────────────────────────────────────
label = ticker_display(selected)

MA_MIN_DAYS = {5: 5, 10: 10, 20: 22, 30: 33, 60: 65, 200: 210}
PERIOD_DAYS = {"1mo": 22, "3mo": 65, "6mo": 130, "1y": 252, "2y": 504, "5y": 1260}

effective_period = period
if selected_mas:
    needed = max(MA_MIN_DAYS.get(m, m) for m in selected_mas)
    if needed > PERIOD_DAYS[period]:
        for p in ("3mo", "6mo", "1y", "2y", "5y"):
            if PERIOD_DAYS[p] >= needed:
                effective_period = p
                break
        st.caption(f"⚠️ MA{max(selected_mas)} 需較長資料，已自動延伸至「{effective_period}」")

hist = get_historical_data(selected, period=effective_period)

if hist.empty:
    st.error("無法載入資料，請確認代號是否正確。")
    st.stop()

if chart_type == "K線圖":
    fig = create_candlestick_chart(hist, selected, label=label, mas=selected_mas)
else:
    fig = create_line_chart(hist, selected, label=label, mas=selected_mas)

st.plotly_chart(fig, use_container_width=True)

# ── Info bar ──────────────────────────────────────────────────────────────────
info = get_stock_info(selected)
if info:
    is_tw = info["is_tw"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("現價", format_price(info["price"], is_tw))
    c2.metric("漲跌", f"{info['change']:+.2f}", f"{info['change_pct']:+.2f}%")
    if info.get("week_52_high"):
        c3.metric("52週高", format_price(info["week_52_high"], is_tw))
    if info.get("week_52_low"):
        c4.metric("52週低", format_price(info["week_52_low"], is_tw))

# ── MA legend ────────────────────────────────────────────────────────────────
if selected_mas:
    colors = {5: "#FFD700", 10: "#FFA040", 20: "#00BFFF", 30: "#7FFF00", 60: "#FF69B4", 200: "#FF6347"}
    legend = "　".join(f'<span style="color:{colors[m]}">■</span> MA{m}' for m in selected_mas)
    st.markdown(legend, unsafe_allow_html=True)

# ── Raw data ──────────────────────────────────────────────────────────────────
with st.expander("原始資料（最近 30 筆）"):
    df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = df.index.strftime("%Y-%m-%d")
    df.columns = ["開盤", "最高", "最低", "收盤", "成交量"]
    st.dataframe(df.sort_index(ascending=False).head(30), use_container_width=True)
