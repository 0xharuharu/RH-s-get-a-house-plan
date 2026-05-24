from __future__ import annotations

import re
from datetime import date as _date

import pandas as pd
import streamlit as st

from utils.portfolio import (
    load_portfolio, save_portfolio,
    get_profile_name, get_profile_pin_hash, verify_pin,
    get_profile_holdings,
    get_capital, set_capital, get_target_pct, set_target_pct,
    get_transactions,
)
from utils.stock_data import get_stock_info, TW_NAMES, get_usd_twd_rate_detail

st.set_page_config(page_title="倉位規劃", page_icon="📐", layout="wide")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
portfolio = st.session_state.portfolio

st.markdown(
    """<style>[data-testid="InputInstructions"] { display: none !important; }</style>""",
    unsafe_allow_html=True,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_tw_ticker(ticker: str) -> bool:
    if ticker.endswith(".TW") or ticker.endswith(".TWO"):
        return True
    if re.match(r"^\d+[A-Z]?$", ticker):
        return True
    if any("一" <= c <= "鿿" for c in ticker):
        return True
    return False


def _price_for(ticker: str, holdings: dict) -> float | None:
    info = get_stock_info(ticker)
    if not info and ticker.endswith(".TW"):
        info = get_stock_info(ticker.replace(".TW", ".TWO"))
    if info:
        return info["price"]
    # fall back to cost so unrealized P&L shows zero (not None)
    h = holdings.get(ticker)
    return h["cost_per_share"] if h else None


# ── PIN gate (shared session state with 持倉管理) ─────────────────────────────

def render_pin_gate(profile_id: str, profile_name: str) -> bool:
    session_key = f"{profile_id}_unlocked"
    pin_hash = get_profile_pin_hash(portfolio, profile_id)
    if not pin_hash:
        return True
    if st.session_state.get(session_key):
        lock_col, _ = st.columns([2, 8])
        with lock_col:
            if st.button("🔒 鎖定", key=f"pos_{profile_id}_lock",
                         type="secondary", use_container_width=True):
                st.session_state[session_key] = False
                st.rerun()
        return True
    st.markdown(
        f"""<div style='text-align:center;padding:56px 0 22px'>
            <div style='font-size:2.8em;margin-bottom:16px;opacity:0.75'>🔒</div>
            <div style='font-size:1.08em;font-weight:700;color:#ddd;
                        letter-spacing:0.04em;margin-bottom:6px'>{profile_name}</div>
            <div style='font-size:0.82em;color:#6b6b6b'>
                輸入 4 位數字密碼以解鎖
            </div></div>""",
        unsafe_allow_html=True,
    )
    _, col_i, _ = st.columns([3, 4, 3])
    with col_i:
        pin_val = st.text_input(
            "密碼", type="password", max_chars=4,
            key=f"pos_{profile_id}_pin", label_visibility="collapsed",
            placeholder="輸入密碼",
        )
        st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
        if st.button("解鎖", key=f"pos_{profile_id}_unlock",
                     type="primary", use_container_width=True):
            if pin_val and verify_pin(pin_val, pin_hash):
                st.session_state[session_key] = True
                st.rerun()
            else:
                st.error("密碼錯誤，請再試一次")
    return False


# ── Transaction log renderer ──────────────────────────────────────────────────

def render_tx_log(transactions: list[dict]):
    st.subheader("📋 交易紀錄")
    if not transactions:
        st.caption(
            "尚無交易紀錄。從「持倉管理」頁面買入或賣出後，紀錄將自動出現在此。"
        )
        return

    action_map = {"buy": "📈 買入", "sell": "📉 賣出"}
    rows = []
    for tx in reversed(transactions):
        realized = tx.get("realized_pnl")
        cb = tx.get("cost_basis")
        rows.append({
            "日期": tx.get("date", ""),
            "股票": tx.get("ticker", ""),
            "操作": action_map.get(tx.get("action", ""), tx.get("action", "")),
            "股數": f"{tx.get('qty', 0):,.0f}",
            "成交價": f"{tx.get('price', 0):,.2f}",
            "成本均價": f"{cb:,.2f}" if cb is not None else "—",
            "實現損益": f"{realized:+,.0f}" if realized is not None else "—",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ── Per-profile allocation tab ────────────────────────────────────────────────

def render_allocation_tab(profile_id: str):
    profile_name = get_profile_name(portfolio, profile_id)
    if not render_pin_gate(profile_id, profile_name):
        return

    holdings = get_profile_holdings(portfolio, profile_id)
    capital = get_capital(portfolio, profile_id)
    target_pct = get_target_pct(portfolio, profile_id)
    transactions = get_transactions(portfolio, profile_id)

    # ── Settings ──────────────────────────────────────────────────────────────
    with st.expander("⚙️ 資金與目標設定", expanded=(capital == 0)):
        s1, s2 = st.columns(2)
        with s1:
            new_capital = st.number_input(
                "可投資資金（台幣）",
                value=float(capital), min_value=0.0,
                step=10000.0, format="%.0f",
                key=f"cap_input_{profile_id}",
                help="用於股票投資的總資金（以台幣計）",
            )
        with s2:
            new_target = st.number_input(
                "目標倉位比例（%）",
                value=float(target_pct), min_value=0.0, max_value=100.0,
                step=5.0, format="%.0f",
                key=f"tgt_input_{profile_id}",
                help="希望部署的資金比例，例如 80 代表八成",
            )
        if st.button("💾 儲存設定", key=f"save_setting_{profile_id}", type="primary"):
            set_capital(portfolio, profile_id, new_capital)
            set_target_pct(portfolio, profile_id, new_target)
            save_portfolio(portfolio)
            st.toast("設定已儲存")
            st.rerun()

    if not holdings:
        st.info("尚無持股紀錄，請先至「持倉管理」新增。")
        render_tx_log(transactions)
        return

    # ── Fetch prices ──────────────────────────────────────────────────────────
    with st.spinner("載入價格中…"):
        prices: dict[str, float] = {}
        for t in holdings:
            p = _price_for(t, holdings)
            if p is not None:
                prices[t] = p

    tw_h = {t: h for t, h in holdings.items() if is_tw_ticker(t)}
    us_h = {t: h for t, h in holdings.items() if not is_tw_ticker(t)}

    tw_cost = sum(h["cost_per_share"] * h["quantity"] for h in tw_h.values())
    tw_mkt  = sum(prices.get(t, h["cost_per_share"]) * h["quantity"] for t, h in tw_h.items())

    us_cost_usd = sum(h["cost_per_share"] * h["quantity"] for h in us_h.values())
    us_mkt_usd  = sum(prices.get(t, h["cost_per_share"]) * h["quantity"] for t, h in us_h.items())

    usd_twd = 32.0
    fx_date = ""
    if us_h:
        with st.spinner("載入匯率…"):
            usd_twd, fx_date = get_usd_twd_rate_detail()

    us_cost_twd = us_cost_usd * usd_twd
    us_mkt_twd  = us_mkt_usd  * usd_twd

    total_cost_twd = tw_cost + us_cost_twd
    total_mkt_twd  = tw_mkt  + us_mkt_twd
    unrealized_twd = total_mkt_twd - total_cost_twd

    # Realized P&L from log (convert USD sells to TWD)
    realized_tw  = sum(
        tx["realized_pnl"] for tx in transactions
        if tx.get("realized_pnl") is not None and is_tw_ticker(tx["ticker"])
    )
    realized_us_usd = sum(
        tx["realized_pnl"] for tx in transactions
        if tx.get("realized_pnl") is not None and not is_tw_ticker(tx["ticker"])
    )
    realized_twd   = realized_tw + realized_us_usd * usd_twd
    total_pnl_twd  = unrealized_twd + realized_twd

    # ── Allocation dashboard ──────────────────────────────────────────────────
    st.subheader("📊 倉位狀態")

    # Read updated capital/target (user might have just saved)
    capital    = get_capital(portfolio, profile_id)
    target_pct = get_target_pct(portfolio, profile_id)

    if capital > 0:
        target_amt   = capital * target_pct / 100
        cost_vs_tgt  = (total_cost_twd / target_amt * 100) if target_amt > 0 else 0
        gap_cost     = target_amt - total_cost_twd
        reached      = cost_vs_tgt >= 100

        # ── Top metrics ───────────────────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("可投資資金", f"NT${capital:,.0f}")
        m2.metric(f"目標投入金額（{target_pct:.0f}%）", f"NT${target_amt:,.0f}")
        m3.metric("已投入成本", f"NT${total_cost_twd:,.0f}",
                  f"達成目標 {cost_vs_tgt:.1f}%", delta_color="off")
        if reached:
            m4.metric("距目標差距", "✅ 已達標")
        else:
            m4.metric("距目標差距", f"NT${gap_cost:,.0f}",
                      f"還需投入 {gap_cost / target_amt * 100:.1f}%",
                      delta_color="off")

        # ── Progress bar: invested cost vs target ─────────────────────────────
        fill  = min(cost_vs_tgt, 100)
        clr   = "#21c55d" if reached else "#4dabf5"
        gap_s = (
            "<span style='color:#21c55d'>✅ 已達標</span>"
            if reached
            else f"<span style='color:#f59f00'>還差 NT${gap_cost:,.0f}</span>"
        )
        hint = (
            f"= 已投入成本 NT${total_cost_twd:,.0f} ÷ 目標金額 NT${target_amt:,.0f}"
            f"　｜僅買賣時改變，不受股價影響"
        )
        st.markdown(
            f"<div style='margin:14px 0 4px'>"
            f"<div style='display:flex;justify-content:space-between;"
            f"font-size:0.82em;opacity:0.6;margin-bottom:4px'>"
            f"<span>目標投入進度</span>"
            f"<span>{cost_vs_tgt:.1f}% / 100%　{gap_s}</span></div>"
            f"<div style='height:8px;border-radius:4px;"
            f"background:rgba(128,128,128,0.18);overflow:hidden'>"
            f"<div style='height:100%;width:{fill:.1f}%;"
            f"background:{clr};border-radius:4px'></div></div>"
            f"<div style='font-size:0.74em;opacity:0.40;margin-top:4px'>{hint}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ── Market value vs cost comparison ───────────────────────────────────
        mv_diff   = total_mkt_twd - total_cost_twd
        mv_pct_d  = (mv_diff / total_cost_twd * 100) if total_cost_twd else 0
        mv_sign   = "▲" if mv_diff >= 0 else "▼"
        mv_clr    = "#ff4b4b" if mv_diff >= 0 else "#21c55d"
        mv_bg     = "rgba(255,75,75,0.06)"  if mv_diff >= 0 else "rgba(33,197,93,0.06)"
        mv_border = "rgba(255,75,75,0.18)"  if mv_diff >= 0 else "rgba(33,197,93,0.18)"
        st.markdown(
            f"<div style='background:{mv_bg};border:1px solid {mv_border};"
            f"border-radius:8px;padding:10px 14px;margin:2px 0 12px'>"
            f"<div style='font-size:0.76em;opacity:0.50;margin-bottom:5px'>"
            f"📊 市值 vs 成本（目前持股的浮動盈虧）</div>"
            f"<div style='display:flex;align-items:center;flex-wrap:wrap;gap:6px 12px'>"
            f"<span style='font-size:0.88em'>市值 <b>NT${total_mkt_twd:,.0f}</b></span>"
            f"<span style='opacity:0.30'>vs</span>"
            f"<span style='font-size:0.88em'>成本 <b>NT${total_cost_twd:,.0f}</b></span>"
            f"<span style='font-size:1.05em;font-weight:700;color:{mv_clr}'>"
            f"{mv_sign} NT${abs(mv_diff):,.0f}　{mv_pct_d:+.2f}%"
            f"</span></div></div>",
            unsafe_allow_html=True,
        )

        if us_h and fx_date:
            st.caption(f"匯率 1 USD = NT${usd_twd:.4f}（{fx_date}）")

        # ── TW / US breakdown (only when both markets present) ────────────────
        if tw_h and us_h:
            st.markdown("**台美股配比**")
            tw_mkt_pct  = tw_mkt     / total_mkt_twd  * 100 if total_mkt_twd  else 0
            us_mkt_pct  = us_mkt_twd / total_mkt_twd  * 100 if total_mkt_twd  else 0
            tw_cost_pct = tw_cost    / total_cost_twd * 100 if total_cost_twd else 0
            us_cost_pct = us_cost_twd/ total_cost_twd * 100 if total_cost_twd else 0

            def _market_card(flag: str, name: str, mkt: float, cost: float,
                             mkt_p: float, cost_p: float, border_clr: str) -> str:
                return (
                    f"<div style='background:rgba(128,128,128,0.04);"
                    f"border:1px solid {border_clr};border-radius:8px;padding:12px 14px'>"
                    f"<div style='font-size:0.80em;opacity:0.55;margin-bottom:5px'>{flag} {name}</div>"
                    f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:6px'>"
                    f"<div><div style='font-size:0.75em;opacity:0.5'>市值（TWD）</div>"
                    f"<div style='font-size:1.05em;font-weight:700'>NT${mkt:,.0f}</div>"
                    f"<div style='font-size:0.78em;opacity:0.65'>佔總市值 {mkt_p:.1f}%</div></div>"
                    f"<div><div style='font-size:0.75em;opacity:0.5'>投入成本（TWD）</div>"
                    f"<div style='font-size:1.05em;font-weight:700'>NT${cost:,.0f}</div>"
                    f"<div style='font-size:0.78em;opacity:0.65'>佔總成本 {cost_p:.1f}%</div></div>"
                    f"</div></div>"
                )

            st.markdown(
                f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:8px 0'>"
                + _market_card("🇹🇼", "台股", tw_mkt, tw_cost,
                               tw_mkt_pct, tw_cost_pct, "rgba(77,171,245,0.2)")
                + _market_card("🇺🇸", "美股（換算台幣）", us_mkt_twd, us_cost_twd,
                               us_mkt_pct, us_cost_pct, "rgba(245,159,0,0.2)")
                + "</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("請先在上方設定可投資資金，以查看倉位分析。")

    st.divider()

    # ── P&L summary ───────────────────────────────────────────────────────────
    st.subheader("💹 損益摘要")

    unrealized_pct   = (unrealized_twd / total_cost_twd * 100) if total_cost_twd else 0
    total_return_pct = (total_pnl_twd   / total_cost_twd * 100) if total_cost_twd else 0

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("未實現損益", f"NT${unrealized_twd:+,.0f}")
    p2.metric("未實現報酬率", f"{unrealized_pct:+.2f}%")
    p3.metric("已實現損益", f"NT${realized_twd:+,.0f}")
    p4.metric("總損益", f"NT${total_pnl_twd:+,.0f}", f"{total_return_pct:+.2f}%")

    if transactions:
        try:
            earliest = min(tx["date"] for tx in transactions if tx.get("date"))
            days = (_date.today() - _date.fromisoformat(earliest)).days
            if days > 0 and total_cost_twd > 0:
                r = total_pnl_twd / total_cost_twd
                if days >= 30:
                    ann = ((1 + r) ** (365 / days) - 1) * 100
                    st.caption(
                        f"年化報酬率：{ann:+.2f}%"
                        f"（自 {earliest} 起，{days} 天）"
                    )
                else:
                    st.caption(
                        f"持倉未滿 30 天（{days} 天），總報酬率：{r * 100:+.2f}%"
                    )
        except Exception:
            pass

    st.divider()

    # ── Transaction log ───────────────────────────────────────────────────────
    render_tx_log(transactions)


# ── Main ──────────────────────────────────────────────────────────────────────

st.header("📐 倉位規劃")

name_a = get_profile_name(portfolio, "profile_a")
name_b = get_profile_name(portfolio, "profile_b")

tab_a, tab_b = st.tabs([f"👤 {name_a}", f"👤 {name_b}"])

with tab_a:
    render_allocation_tab("profile_a")

with tab_b:
    render_allocation_tab("profile_b")
