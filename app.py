from __future__ import annotations

import streamlit as st
from utils.portfolio import load_portfolio

st.set_page_config(
    page_title="股票 Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/* ── Compact layout (values injected by Python below) ── */
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1440px;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 12px 16px;
}

/* ── Containers / cards ── */
[data-testid="stVerticalBlockBorderWrapper"] > div {
    border-radius: 10px !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    border-right: 1px solid rgba(255,255,255,0.08);
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab"] {
    border-radius: 6px 6px 0 0;
    padding: 6px 18px;
    font-size: 0.93em;
}

/* ── Dividers ── */
hr { border-color: rgba(255,255,255,0.08); }

/* ── Stock name hyperlinks (query-param nav) ── */
.stock-link a {
    color: inherit !important;
    text-decoration: none !important;
}
.stock-link a:hover {
    text-decoration: underline !important;
    opacity: 0.85;
}

/* ── Caption text ── */
[data-testid="stCaptionContainer"] p {
    color: rgba(255,255,255,0.55);
    font-size: 0.82em;
}
</style>
""", unsafe_allow_html=True)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()

s = st.session_state.portfolio.get("settings", {})
_display = s.get("display", {})
_font_px = _display.get("base_font_px", 15)
_compact = _display.get("compact", False)
_padding = "0.6rem" if _compact else "1.2rem"

# Dynamic user display preferences
st.markdown(
    f"<style>"
    f".block-container{{padding-top:{_padding};font-size:{_font_px}px;}}"
    f"[data-testid='stSidebar'] .block-container{{padding-top:1rem;}}"
    f"</style>",
    unsafe_allow_html=True,
)

pg = st.navigation([
    st.Page("pages/0_首頁.py",    title=s.get("home_page_name",     "首頁"),    icon="🏠", default=True),
    st.Page("pages/1_台股.py",    title=s.get("tw_page_name",       "台股"),    icon="🇹🇼"),
    st.Page("pages/2_美股.py",    title=s.get("us_page_name",       "美股"),    icon="🇺🇸"),
    st.Page("pages/3_K線圖.py",   title=s.get("chart_page_name",    "K線圖"),   icon="📈"),
    st.Page("pages/4_持倉管理.py", title=s.get("holdings_page_name", "持倉管理"), icon="💼"),
    st.Page("pages/6_全球股市.py",       title=s.get("global_page_name",  "全球股市"),   icon="🌍"),
    st.Page("pages/7_個股詳細資訊.py",  title=s.get("detail_page_name",  "個股詳細資訊"), icon="🔍"),
    st.Page("pages/5_設定.py",          title=s.get("settings_page_name","設定"),        icon="⚙️"),
])
pg.run()
