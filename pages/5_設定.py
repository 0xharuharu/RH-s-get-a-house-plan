from __future__ import annotations

import streamlit as st
from utils.portfolio import (
    load_portfolio, save_portfolio,
    get_custom_name_map, set_custom_name_map_entry, remove_custom_name_map_entry,
    get_profile_name, set_profile_name,
    get_profile_pin_hash, set_profile_pin, clear_profile_pin, verify_pin,
)

st.set_page_config(page_title="設定", page_icon="⚙️", layout="wide")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
portfolio = st.session_state.portfolio
settings = portfolio.setdefault("settings", {})

st.title("⚙️ 設定")

# ── 個人設定（雙持倉 + 密碼）─────────────────────────────────────────────────────
st.subheader("🔐 個人設定")
st.caption("為兩位使用者設定各自的顯示名稱與 4 位數字密碼，密碼儲存於本機 portfolio.json，不會上傳。")


def _profile_settings(profile_id: str, default_name: str):
    current_name = get_profile_name(portfolio, profile_id)
    pin_hash = get_profile_pin_hash(portfolio, profile_id)

    with st.container(border=True):
        st.markdown(f"**{current_name}** `({profile_id})`")

        # ── Name ─────────────────────────────────────────────────────────────
        with st.expander("✏️ 更改名稱"):
            with st.form(f"form_name_{profile_id}"):
                new_name = st.text_input(
                    "新名稱",
                    value=current_name,
                    key=f"prof_name_{profile_id}",
                    max_chars=20,
                )
                if st.form_submit_button("儲存名稱", type="primary"):
                    clean = new_name.strip()
                    if clean:
                        set_profile_name(portfolio, profile_id, clean)
                        save_portfolio(portfolio)
                        st.success(f"已儲存：{clean}")
                        st.rerun()

        # ── PIN ───────────────────────────────────────────────────────────────
        if not pin_hash:
            st.caption("🔓 目前無密碼保護")
            with st.expander("🔑 設定密碼"):
                with st.form(f"form_set_pin_{profile_id}"):
                    p1 = st.text_input(
                        "新密碼（4 位數字）",
                        type="password",
                        max_chars=4,
                        key=f"pin_new_{profile_id}",
                    )
                    p2 = st.text_input(
                        "確認新密碼",
                        type="password",
                        max_chars=4,
                        key=f"pin_confirm_{profile_id}",
                    )
                    if st.form_submit_button("設定密碼", type="primary"):
                        if not p1 or not p1.isdigit() or len(p1) != 4:
                            st.error("請輸入 4 位數字密碼")
                        elif p1 != p2:
                            st.error("兩次輸入不一致")
                        else:
                            set_profile_pin(portfolio, profile_id, p1)
                            # Clear any existing unlock state
                            st.session_state.pop(f"{profile_id}_unlocked", None)
                            save_portfolio(portfolio)
                            st.success("密碼已設定")
                            st.rerun()
        else:
            st.caption("🔒 已設定密碼保護")
            with st.expander("🔑 變更密碼"):
                with st.form(f"form_change_pin_{profile_id}"):
                    old_p = st.text_input(
                        "目前密碼",
                        type="password",
                        max_chars=4,
                        key=f"pin_old_{profile_id}",
                    )
                    p1 = st.text_input(
                        "新密碼（4 位數字）",
                        type="password",
                        max_chars=4,
                        key=f"pin_new_{profile_id}",
                    )
                    p2 = st.text_input(
                        "確認新密碼",
                        type="password",
                        max_chars=4,
                        key=f"pin_confirm_{profile_id}",
                    )
                    if st.form_submit_button("變更密碼", type="primary"):
                        if not verify_pin(old_p, pin_hash):
                            st.error("目前密碼錯誤")
                        elif not p1 or not p1.isdigit() or len(p1) != 4:
                            st.error("新密碼需為 4 位數字")
                        elif p1 != p2:
                            st.error("兩次輸入不一致")
                        else:
                            set_profile_pin(portfolio, profile_id, p1)
                            st.session_state.pop(f"{profile_id}_unlocked", None)
                            save_portfolio(portfolio)
                            st.success("密碼已更新")
                            st.rerun()

            with st.expander("🗑️ 移除密碼"):
                with st.form(f"form_clear_pin_{profile_id}"):
                    confirm_p = st.text_input(
                        "輸入目前密碼以確認移除",
                        type="password",
                        max_chars=4,
                        key=f"pin_clear_{profile_id}",
                    )
                    if st.form_submit_button("移除密碼保護", type="secondary"):
                        if verify_pin(confirm_p, pin_hash):
                            clear_profile_pin(portfolio, profile_id)
                            st.session_state.pop(f"{profile_id}_unlocked", None)
                            save_portfolio(portfolio)
                            st.success("密碼已移除")
                            st.rerun()
                        else:
                            st.error("密碼錯誤")


col_prof_a, col_prof_b = st.columns(2)
with col_prof_a:
    _profile_settings("profile_a", "HARU")
with col_prof_b:
    _profile_settings("profile_b", "RAY")

st.divider()

# ── Dashboard 名稱 ─────────────────────────────────────────────────────────────
st.subheader("基本設定")

PAGE_DEFAULTS = {
    "dashboard_name":    ("Dashboard 標題（首頁大標題）",   "股票 Dashboard"),
    "home_page_name":    ("首頁",                          "首頁"),
    "tw_page_name":      ("台股",                          "台股"),
    "us_page_name":      ("美股",                          "美股"),
    "chart_page_name":   ("K線圖",                         "K線圖"),
    "holdings_page_name":("持倉管理",                      "持倉管理"),
    "global_page_name":  ("全球股市",                      "全球股市"),
    "detail_page_name":  ("個股詳細資訊",                  "個股詳細資訊"),
    "settings_page_name":("設定",                          "設定"),
}

with st.form("form_name"):
    st.caption("修改後請重新整理頁面，側邊欄名稱才會更新。")
    inputs = {}
    for key, (label, default) in PAGE_DEFAULTS.items():
        inputs[key] = st.text_input(label, value=settings.get(key, default))
    if st.form_submit_button("儲存所有名稱", type="primary"):
        for key, (_, default) in PAGE_DEFAULTS.items():
            settings[key] = inputs[key].strip() or default
        save_portfolio(portfolio)
        st.success("已儲存，請重新整理頁面讓側邊欄名稱生效")

st.divider()

# ── 自訂名稱對照 ──────────────────────────────────────────────────────────────────
st.subheader("🔤 自訂名稱對照")
st.caption("當持倉以中文名稱儲存（如「穩懋」）但系統找不到代號時，在此手動指定。優先級最高，會覆蓋內建對照表。")

custom_map = get_custom_name_map(portfolio)

if custom_map:
    st.markdown("**現有對照**")
    for name, ticker in list(custom_map.items()):
        c1, c2, c3 = st.columns([3, 3, 1])
        with c1:
            st.markdown(f"**{name}**")
        with c2:
            st.caption(ticker)
        with c3:
            if st.button("刪除", key=f"del_cmap_{name}", type="secondary", use_container_width=True):
                remove_custom_name_map_entry(portfolio, name)
                save_portfolio(portfolio)
                st.rerun()
else:
    st.caption("尚無自訂對照。")

with st.expander("➕ 新增對照"):
    with st.form("form_custom_map"):
        cm1, cm2 = st.columns(2)
        with cm1:
            cn_name = st.text_input("中文名稱（與持倉 key 完全相同）", placeholder="例：穩懋")
        with cm2:
            cn_ticker = st.text_input("正確代號", placeholder="例：3105.TW")
        if st.form_submit_button("新增", type="primary"):
            n, t = cn_name.strip(), cn_ticker.strip().upper()
            if n and t:
                set_custom_name_map_entry(portfolio, n, t)
                save_portfolio(portfolio)
                st.success(f"已新增：{n} → {t}")
                st.rerun()

st.divider()


# ── 共用：群組編輯區 ────────────────────────────────────────────────────────────
def render_group_editor(market: str, label: str):
    st.subheader(label)
    key = f"{market}_groups"
    groups: dict[str, list] = portfolio.get(key, {})

    if not groups:
        st.info("尚無群組。")
    else:
        for grp in list(groups.keys()):
            c1, c2, c3, c4 = st.columns([4, 2, 1, 1])

            with c1:
                new_name = st.text_input(
                    "名稱",
                    value=grp,
                    key=f"{market}_name_{grp}",
                    label_visibility="collapsed",
                )
            with c2:
                ticker_count = len(groups[grp])
                tickers_preview = ", ".join(groups[grp][:3])
                if ticker_count > 3:
                    tickers_preview += f" ...共 {ticker_count} 支"
                elif ticker_count == 0:
                    tickers_preview = "（空群組）"
                st.caption(tickers_preview)
            with c3:
                if st.button("重命名", key=f"{market}_rename_{grp}", use_container_width=True):
                    clean = new_name.strip()
                    if clean and clean != grp and clean not in groups:
                        ordered = {
                            (clean if k == grp else k): v
                            for k, v in groups.items()
                        }
                        portfolio[key] = ordered
                        save_portfolio(portfolio)
                        st.rerun()
                    elif clean in groups and clean != grp:
                        st.warning("名稱已存在")
            with c4:
                if st.button("刪除", key=f"{market}_del_{grp}", use_container_width=True, type="secondary"):
                    if groups[grp]:
                        st.warning(f"「{grp}」含 {len(groups[grp])} 支股票，請先移除後再刪除。")
                    else:
                        del portfolio[key][grp]
                        save_portfolio(portfolio)
                        st.rerun()

    st.markdown("")
    with st.expander("➕ 新增群組"):
        with st.form(f"form_add_{market}"):
            new_grp = st.text_input("新群組名稱", key=f"{market}_new_grp_name")
            if st.form_submit_button("建立"):
                name = new_grp.strip()
                if name and name not in portfolio[key]:
                    portfolio[key][name] = []
                    save_portfolio(portfolio)
                    st.rerun()
                elif name in portfolio[key]:
                    st.warning("群組已存在")


render_group_editor("tw", "🇹🇼 台股群組")
st.divider()
render_group_editor("us", "🇺🇸 美股群組")

st.divider()

# ── API 金鑰 ──────────────────────────────────────────────────────────────────
st.subheader("🔑 新聞 API 金鑰")
st.caption("設定後可在「個股詳細資訊」取得更完整的英文新聞（含情緒分析）。金鑰儲存於本機 portfolio.json，不會上傳。")

api_keys = portfolio.setdefault("api_keys", {})

with st.form("form_api_keys"):
    c_av, c_fh = st.columns(2)
    with c_av:
        av_input = st.text_input(
            "Alpha Vantage API Key",
            value=api_keys.get("alpha_vantage", ""),
            type="password",
            help="25次/天免費，美股情緒分析",
        )
    with c_fh:
        fh_input = st.text_input(
            "Finnhub API Key",
            value=api_keys.get("finnhub", ""),
            type="password",
            help="60次/分鐘免費，美股新聞最完整",
        )
    if st.form_submit_button("儲存 API 金鑰", type="primary"):
        api_keys["alpha_vantage"] = av_input.strip()
        api_keys["finnhub"] = fh_input.strip()
        save_portfolio(portfolio)
        st.success("已儲存")

col_av, col_fh = st.columns(2)
with col_av:
    if api_keys.get("alpha_vantage"):
        st.success(f"✅ Alpha Vantage（...{api_keys['alpha_vantage'][-4:]}）")
    with st.expander("如何申請 Alpha Vantage？"):
        st.markdown(
            "1. 前往 **[alphavantage.co](https://www.alphavantage.co/support/#api-key)**\n"
            "2. 填入姓名 + Email，立即取得\n"
            "3. 免費版：25次/天，5次/分\n"
            "4. 支援美股新聞 + 情緒分析標籤"
        )
with col_fh:
    if api_keys.get("finnhub"):
        st.success(f"✅ Finnhub（...{api_keys['finnhub'][-4:]}）")
    with st.expander("如何申請 Finnhub？"):
        st.markdown(
            "1. 前往 **[finnhub.io/register](https://finnhub.io/register)**\n"
            "2. 填入 Email 免費註冊\n"
            "3. 免費版：60次/分鐘，美股新聞最完整\n"
            "4. **台股不支援**（.TW 股票請用鉅亨網，不需 API）"
        )

st.divider()

# ── 顯示設定 ──────────────────────────────────────────────────────────────────
st.subheader("🎨 顯示設定")
st.caption("調整後請點「套用」並重新整理頁面。")

display = settings.setdefault("display", {})

_font_map = {"小 (13px)": 13, "中 (15px)": 15, "大 (17px)": 17}
_font_rev = {v: k for k, v in _font_map.items()}
curr_font_label = _font_rev.get(display.get("base_font_px", 15), "中 (15px)")

with st.form("form_display"):
    d1, d2 = st.columns(2)
    with d1:
        chosen_font = st.select_slider(
            "基礎字體大小",
            options=list(_font_map.keys()),
            value=curr_font_label,
            help="影響卡片說明文字、數據等一般文字大小",
        )
    with d2:
        compact = st.checkbox(
            "精簡模式（減少留白）",
            value=display.get("compact", False),
            help="縮小各元件間距，顯示更多內容",
        )
    if st.form_submit_button("套用顯示設定", type="primary"):
        display["base_font_px"] = _font_map[chosen_font]
        display["compact"] = compact
        save_portfolio(portfolio)
        st.success("已套用！請重新整理頁面（F5 / Cmd+R）。")
        st.rerun()
