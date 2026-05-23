from __future__ import annotations

import streamlit as st
from utils.portfolio import load_portfolio

st.set_page_config(
    page_title="股票 Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown("""
<style>
/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { display: none !important; }
[data-testid="stToolbar"]  { display: none !important; }
/* Streamlit Community Cloud bottom badge (always hidden) */
[class*="viewerBadge"]     { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }

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
    padding: 4px 13px;
    font-size: 0.84em;
    font-weight: 500;
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

/* ── Mobile bottom nav (hidden on desktop) ── */
.mobile-bottom-nav { display: none; }

/* ══ Mobile responsive ══════════════════════════════════════════════════════ */
@media (max-width: 640px) {
    /* Tighter page padding + space for nav bar (56px) + Streamlit badge (44px) */
    .block-container {
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        padding-top: 0.75rem !important;
        padding-bottom: 7rem !important;
        max-width: 100vw !important;
    }
    /* Smaller headings */
    h1 { font-size: 1.35rem !important; }
    h2 { font-size: 1.1rem !important; }
    h3 { font-size: 0.95rem !important; }
    /* Compact metric cards */
    [data-testid="metric-container"] {
        padding: 8px 10px !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.0rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.70rem !important;
    }
    /* Allow columns to wrap when too narrow for screen */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }
    [data-testid="column"] {
        min-width: 100px !important;
    }
    /* Tabs: smaller text */
    .stTabs [data-baseweb="tab"] {
        padding: 4px 10px !important;
        font-size: 0.85em !important;
    }
    /* Expanders: less padding */
    [data-testid="stExpander"] summary {
        padding: 8px 12px !important;
    }
    /* ── Bottom navigation bar ──
       Sits above the Streamlit Cloud badge (~44px) by using bottom:44px.
       This is more reliable than z-index tricks because the badge is
       injected outside the app's CSS scope.                            ── */
    .mobile-bottom-nav {
        display: flex;
        position: fixed;
        bottom: 44px;          /* above Streamlit Cloud badge bar     */
        left: 0;
        right: 0;
        height: 56px;
        background: #0e1117;
        border-top: 1px solid rgba(255,255,255,0.13);
        z-index: 2147483647;
        align-items: stretch;
        padding-bottom: env(safe-area-inset-bottom, 0px);
    }
    .mobile-bottom-nav a {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: rgba(255,255,255,0.50);
        text-decoration: none;
        font-size: 0.58rem;
        gap: 1px;
        -webkit-tap-highlight-color: transparent;
        transition: color 0.12s, background 0.12s;
    }
    .mobile-bottom-nav a:active {
        color: #fff;
        background: rgba(255,255,255,0.06);
    }
    .nav-icon {
        font-size: 1.3rem;
        line-height: 1.3;
    }
    /* Fill the gap between nav bar and Streamlit badge with same background */
    .mobile-bottom-nav::after {
        content: '';
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        height: 44px;
        background: #0e1117;
        z-index: 2147483646;
    }
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
    st.Page("pages/0_首頁.py",         title=s.get("home_page_name",     "首頁"),        icon="🏠", default=True),
    st.Page("pages/1_台股.py",         title=s.get("tw_page_name",       "台股"),        icon="🇹🇼", url_path="tw"),
    st.Page("pages/2_美股.py",         title=s.get("us_page_name",       "美股"),        icon="🇺🇸", url_path="us"),
    st.Page("pages/3_K線圖.py",        title=s.get("chart_page_name",    "K線圖"),       icon="📈", url_path="chart"),
    st.Page("pages/4_持倉管理.py",     title=s.get("holdings_page_name", "持倉管理"),    icon="💼", url_path="holdings"),
    st.Page("pages/6_全球股市.py",     title=s.get("global_page_name",   "全球股市"),    icon="🌍", url_path="global"),
    st.Page("pages/7_個股詳細資訊.py", title=s.get("detail_page_name",   "個股詳細資訊"), icon="🔍", url_path="detail"),
    st.Page("pages/5_設定.py",         title=s.get("settings_page_name", "設定"),        icon="⚙️", url_path="settings"),
])

# Mobile bottom navigation bar (fixed, only visible on ≤640px screens)
st.markdown("""
<nav class="mobile-bottom-nav">
    <a href="/">
        <span class="nav-icon">🏠</span>首頁
    </a>
    <a href="/tw">
        <span class="nav-icon">🇹🇼</span>台股
    </a>
    <a href="/us">
        <span class="nav-icon">🇺🇸</span>美股
    </a>
    <a href="/holdings">
        <span class="nav-icon">💼</span>持倉
    </a>
    <a href="/global">
        <span class="nav-icon">🌍</span>全球
    </a>
    <a href="/settings">
        <span class="nav-icon">⚙️</span>設定
    </a>
</nav>
""", unsafe_allow_html=True)

pg.run()
