from __future__ import annotations

import re
import streamlit as st
import plotly.express as px

from utils.portfolio import (
    load_portfolio, save_portfolio,
    get_custom_name_map, set_custom_name_map_entry, remove_custom_name_map_entry,
    get_profile_name, get_profile_pin_hash, verify_pin,
    get_profile_holdings, upsert_profile_holding, remove_profile_holding,
    set_profile_pin, clear_profile_pin,
    log_transaction,
    get_broker_fee_rate, set_broker_fee_rate,
    calc_commission, calc_sell_costs,
)
from utils.stock_data import (
    get_stock_info, TW_NAMES, TW_NAMES_REVERSE,
    get_usd_twd_rate, get_usd_twd_rate_detail,
)

st.set_page_config(page_title="持倉管理", page_icon="💼", layout="wide")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
portfolio = st.session_state.portfolio

# ── Sidebar：手續費設定 ────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 手續費設定")
    current_rate_pct = get_broker_fee_rate(portfolio) * 100
    new_rate_pct = st.number_input(
        "手續費率（%）",
        min_value=0.0,
        max_value=0.1425,
        value=round(current_rate_pct, 5),
        step=0.001,
        format="%.4f",
        help=(
            "台股標準費率 0.1425%。\n"
            "依你的券商折扣填入實際費率：\n"
            "• 6折 → 0.0855%\n"
            "• 28折 → 0.0399%"
        ),
    )
    discount_pct = (new_rate_pct / 0.1425 * 100) if new_rate_pct else 0
    st.caption(f"相當於標準費率的 **{discount_pct:.0f}%**（{discount_pct/10:.1f}折）")
    if st.button("💾 儲存費率", use_container_width=True):
        set_broker_fee_rate(portfolio, new_rate_pct / 100)
        save_portfolio(portfolio)
        st.success("已儲存")
        st.rerun()
    st.caption("※ 賣出手續費 + 0.3% 證交稅將用於計算預估淨損益")

PROFILE_IDS = ["profile_a", "profile_b"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_tw_ticker(ticker: str) -> bool:
    if ticker.endswith(".TW") or ticker.endswith(".TWO"):
        return True
    if re.match(r"^\d+[A-Z]?$", ticker):
        return True
    if any("一" <= c <= "鿿" for c in ticker):
        return True
    return False


def resolve_info(ticker: str) -> dict | None:
    info = get_stock_info(ticker)
    if info:
        return info
    if any("一" <= c <= "鿿" for c in ticker):
        custom_map = get_custom_name_map(portfolio)
        real = custom_map.get(ticker) or TW_NAMES_REVERSE.get(ticker)
        if real:
            return get_stock_info(real)
        return None
    if is_tw_ticker(ticker) and not ticker.endswith(".TW") and not ticker.endswith(".TWO"):
        result = get_stock_info(ticker + ".TW")
        if result:
            return result
        return get_stock_info(ticker + ".TWO")
    if ticker.endswith(".TW"):
        return get_stock_info(ticker.replace(".TW", ".TWO"))
    return None


def holding_label(ticker: str) -> str:
    if any("一" <= c <= "鿿" for c in ticker):
        tw_ticker = TW_NAMES_REVERSE.get(ticker)
        if tw_ticker:
            code = tw_ticker.replace(".TW", "")
            return f"{ticker} {code}.TW"
        return ticker
    info = resolve_info(ticker)
    if info:
        display = info.get("display_name") or info.get("name", ticker)
        full_ticker = (ticker + ".TW") if (is_tw_ticker(ticker) and not ticker.endswith(".TW")) else ticker
        return f"{display} {full_ticker}"
    if ticker in TW_NAMES:
        return f"{TW_NAMES[ticker]} {ticker}"
    if is_tw_ticker(ticker) and not ticker.endswith(".TW"):
        full = ticker + ".TW"
        return f"{TW_NAMES[full]} {full}" if full in TW_NAMES else full
    return ticker


def fmt(value: float) -> str:
    return f"{value:,.2f}"


def tw_pie_label(ticker: str) -> str:
    for key in (ticker, ticker + ".TW"):
        if key in TW_NAMES:
            return TW_NAMES[key]
    custom_map = get_custom_name_map(portfolio)
    for name, t in custom_map.items():
        if t in (ticker, ticker + ".TW"):
            return name
    info = resolve_info(ticker)
    if info:
        return info.get("display_name") or ticker.replace(".TW", "")
    return ticker.replace(".TW", "")


def make_pie(section: dict, title: str, market: str = "tw", colors=None):
    labels = [tw_pie_label(t) if market == "tw" else t for t in section]
    values = [h["cost_per_share"] * h["quantity"] for h in section.values()]
    if not values or sum(values) == 0:
        return None
    fig = px.pie(
        names=labels, values=values, title=title, hole=0.42,
        template="plotly_dark",
        color_discrete_sequence=colors or px.colors.qualitative.Set3,
    )
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(
        height=420, margin=dict(l=10, r=10, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
    )
    return fig


# ── PIN gate ──────────────────────────────────────────────────────────────────

def render_pin_gate(profile_id: str, profile_name: str) -> bool:
    """Render unlock UI. Returns True when the profile is accessible."""
    session_key = f"{profile_id}_unlocked"
    pin_hash = get_profile_pin_hash(portfolio, profile_id)

    if not pin_hash:
        return True  # No PIN configured → always open

    if st.session_state.get(session_key):
        # Already unlocked → compact lock button at top-left
        lock_col, _ = st.columns([2, 8])
        with lock_col:
            if st.button(
                "🔒 鎖定",
                key=f"{profile_id}_lock_btn",
                type="secondary",
                use_container_width=True,
            ):
                st.session_state[session_key] = False
                st.rerun()
        return True

    # ── Locked state ──────────────────────────────────────────────────────────
    st.markdown(
        f"""<div style='text-align:center;padding:56px 0 22px'>
            <div style='font-size:2.8em;margin-bottom:16px;opacity:0.75'>🔒</div>
            <div style='font-size:1.08em;font-weight:700;color:#ddd;
                        letter-spacing:0.04em;margin-bottom:6px'>
                {profile_name}
            </div>
            <div style='font-size:0.82em;color:#6b6b6b;'>
                輸入 4 位數字密碼以解鎖持倉資料
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    _, col_i, _ = st.columns([3, 4, 3])
    with col_i:
        pin_val = st.text_input(
            "密碼",
            type="password",
            max_chars=4,
            key=f"{profile_id}_pin_input",
            label_visibility="collapsed",
            placeholder="輸入密碼",
        )
        st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
        if st.button(
            "解鎖",
            key=f"{profile_id}_unlock_btn",
            type="primary",
            use_container_width=True,
        ):
            if pin_val and verify_pin(pin_val, pin_hash):
                st.session_state[session_key] = True
                st.rerun()
            else:
                st.error("密碼錯誤，請再試一次")
    st.markdown("<div style='padding-bottom:40px'></div>", unsafe_allow_html=True)
    return False


# ── Holdings table ────────────────────────────────────────────────────────────

def render_holdings_section(section: dict, title: str, profile_id: str, prices: dict):
    if not section:
        return

    st.subheader(title)

    total_cost = sum(h["cost_per_share"] * h["quantity"] for h in section.values())
    total_mkt = sum(
        prices.get(t, h["cost_per_share"]) * h["quantity"]
        for t, h in section.items()
    )
    total_pnl = total_mkt - total_cost
    pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0

    # ── 預估賣出淨損益（台股：扣手續費+證交稅）────────────────────────
    fee_rate = get_broker_fee_rate(portfolio)
    total_sell_costs = sum(
        calc_sell_costs(prices.get(t, h["cost_per_share"]), h["quantity"], fee_rate)
        for t, h in section.items()
        if is_tw_ticker(t)
    )
    has_sell_costs = total_sell_costs > 0
    total_net_pnl = total_pnl - total_sell_costs
    net_pnl_pct = (total_net_pnl / total_cost * 100) if total_cost else 0

    if has_sell_costs:
        k1, k2, k3, k4 = st.columns(4)
    else:
        k1, k2, k3 = st.columns(3)

    k1.metric("總投入", f"{total_cost:,.0f}")
    k2.metric("目前市值", f"{total_mkt:,.0f}", f"{total_pnl:+,.0f}")
    k3.metric("損益（未扣費）", f"{total_pnl:+,.0f}", f"{pnl_pct:+.2f}%")
    if has_sell_costs:
        k4.metric("預估淨損益", f"{total_net_pnl:+,.0f}", f"{net_pnl_pct:+.2f}%",
                  help="已扣除賣出手續費 + 0.3% 證交稅的預估損益")

    st.markdown("")

    sorted_items = sorted(
        section.items(),
        key=lambda x: x[1]["cost_per_share"] * x[1]["quantity"],
        reverse=True,
    )

    for ticker, h in sorted_items:
        cost_ps = h["cost_per_share"]
        qty = h["quantity"]
        total = cost_ps * qty
        price = prices.get(ticker)
        mkt_val = (price * qty) if price else None
        pnl = (mkt_val - total) if mkt_val is not None else None
        pnl_p = ((pnl / total * 100) if total else 0) if pnl is not None else None
        pos_pct = (total / total_cost * 100) if total_cost else 0

        chg_p = ((price - cost_ps) / cost_ps * 100) if (price and cost_ps) else None
        price_clr = "#ff4b4b" if (chg_p or 0) >= 0 else "#21c55d"
        price_sign = "▲" if (chg_p or 0) >= 0 else "▼"
        price_part = (
            f"<b>{fmt(price)}</b>&nbsp;&nbsp;"
            f"<span style='color:{price_clr};font-size:0.88em'>{price_sign}{abs(chg_p):.2f}%</span>"
        ) if price else "<b>—</b>"

        # ── 預估淨損益（扣賣出手續費 + 證交稅）──────────────────────
        fee_rate = get_broker_fee_rate(portfolio)
        net_pnl = net_pnl_p = None
        if pnl is not None and price is not None and is_tw_ticker(ticker):
            sell_costs = calc_sell_costs(price, qty, fee_rate)
            net_pnl = pnl - sell_costs
            net_pnl_p = (net_pnl / total * 100) if total else 0

        pnl_part = ""
        if pnl is not None and pnl_p is not None:
            pnl_clr = "#ff4b4b" if pnl >= 0 else "#21c55d"
            pnl_part = (
                f"<span style='color:{pnl_clr};font-size:1.28em;font-weight:700'>{pnl:+,.0f}</span>"
                f"&ensp;<span style='color:{pnl_clr};font-size:1.0em;font-weight:600'>{pnl_p:+.2f}%</span>"
            )
            if net_pnl is not None:
                net_clr = "#ff4b4b" if net_pnl >= 0 else "#21c55d"
                pnl_part += (
                    f"<br><span style='font-size:0.78em;opacity:0.65'>預估賣出淨損益&nbsp;</span>"
                    f"<span style='color:{net_clr};font-size:0.88em;font-weight:600'>"
                    f"{net_pnl:+,.0f}（{net_pnl_p:+.2f}%）</span>"
                    f"<span style='font-size:0.72em;opacity:0.45'>&nbsp;含手續費+證交稅</span>"
                )
        else:
            pnl_part = "<span style='opacity:0.45'>—</span>"

        lbl = "font-size:0.82em;opacity:0.5;margin-bottom:3px"
        val = "font-size:1.1em;font-weight:600"

        mode_key = f"edit_mode_{profile_id}_{ticker}"
        if mode_key not in st.session_state:
            st.session_state[mode_key] = None

        with st.container(border=True):
            st.markdown(
                # ── 標題列：名稱 + 倉位 pill badge ──
                f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:10px'>"
                f"<span style='font-weight:700;font-size:1.22em'>{holding_label(ticker)}</span>"
                f"<span style='background:rgba(77,171,245,0.12);"
                f"border:1px solid rgba(77,171,245,0.3);color:#4dabf5;"
                f"padding:1px 8px;border-radius:10px;font-size:0.76em;font-weight:600'>"
                f"倉位 {pos_pct:.1f}%</span>"
                f"</div>"
                # ── 四格資料：均價｜現價｜持股數｜總投入 ──
                f"<div style='display:grid;grid-template-columns:1fr 1.6fr 1fr 1fr;"
                f"gap:6px 14px;margin-bottom:10px'>"
                f"<div><div style='{lbl}'>均價</div><div style='{val}'>{fmt(cost_ps)}</div></div>"
                f"<div><div style='{lbl}'>現價</div><div style='{val}'>{price_part}</div></div>"
                f"<div><div style='{lbl}'>持股數</div><div style='{val}'>{qty:,.0f} 股</div></div>"
                f"<div><div style='{lbl}'>總投入</div><div style='{val}'>{total:,.0f}</div></div>"
                f"</div>"
                # ── 損益列 ──
                f"<div style='border-top:1px solid rgba(128,128,128,0.13);padding-top:8px'>"
                f"<span style='{lbl}'>損益&ensp;</span>{pnl_part}"
                f"</div>",
                unsafe_allow_html=True,
            )

            # ── 操作面板（預設收合） ───────────────────────────────────────────
            with st.expander("編輯"):
                ab, sb, eb, db = st.columns([3, 3, 3, 1])
                with ab:
                    if st.button("📈 買入", key=f"ab_{profile_id}_{ticker}",
                                 use_container_width=True, help="記錄買入，自動計算新均價"):
                        st.session_state[mode_key] = None if st.session_state[mode_key] == "buy" else "buy"
                        st.rerun()
                with sb:
                    if st.button("📉 賣出", key=f"sb_{profile_id}_{ticker}",
                                 use_container_width=True, help="記錄賣出，減少持股數"):
                        st.session_state[mode_key] = None if st.session_state[mode_key] == "sell" else "sell"
                        st.rerun()
                with eb:
                    if st.button("✏️ 編輯", key=f"eb_{profile_id}_{ticker}",
                                 use_container_width=True, help="直接修改持股數與均價"):
                        st.session_state[mode_key] = None if st.session_state[mode_key] == "edit" else "edit"
                        st.rerun()
                with db:
                    if st.button("✕", key=f"del_{profile_id}_{ticker}",
                                 type="secondary", use_container_width=True, help="移除持股"):
                        remove_profile_holding(portfolio, profile_id, ticker)
                        save_portfolio(portfolio)
                        st.rerun()

                # ── 買入表單 ──────────────────────────────────────────────────
                if st.session_state.get(mode_key) == "buy":
                    fee_rate = get_broker_fee_rate(portfolio)
                    with st.form(key=f"buy_form_{profile_id}_{ticker}"):
                        fc1, fc2 = st.columns(2)
                        with fc1:
                            buy_qty = st.number_input("買入股數", min_value=0.0, step=1.0, format="%.0f")
                        with fc2:
                            buy_price = st.number_input("買入價格", min_value=0.0, value=float(cost_ps), step=0.01)
                        st.caption(
                            f"手續費率 {fee_rate*100:.4f}%（最低 NT$20）— "
                            "手續費自動計入成本，可至左側「手續費設定」調整"
                        )
                        if st.form_submit_button("✅ 確認買入", use_container_width=True, type="primary"):
                            if buy_qty > 0:
                                buy_fee = calc_commission(buy_price * buy_qty, fee_rate)
                                total_buy = buy_price * buy_qty + buy_fee
                                new_qty = qty + buy_qty
                                new_cost = (cost_ps * qty + total_buy) / new_qty
                                upsert_profile_holding(portfolio, profile_id, ticker, new_cost, new_qty)
                                log_transaction(portfolio, profile_id, ticker, "buy", buy_qty, buy_price)
                                save_portfolio(portfolio)
                                st.session_state[mode_key] = None
                                st.toast(f"買入 {buy_qty:,.0f} 股，含手續費 NT${buy_fee:,.0f}，新均價 {new_cost:,.2f}")
                                st.rerun()

                # ── 賣出表單 ──────────────────────────────────────────────────
                elif st.session_state.get(mode_key) == "sell":
                    with st.form(key=f"sell_form_{profile_id}_{ticker}"):
                        sc1, sc2 = st.columns(2)
                        with sc1:
                            sell_qty = st.number_input(
                                f"賣出股數（持有 {qty:,.0f} 股）",
                                min_value=0.0, max_value=float(qty), step=1.0, format="%.0f",
                            )
                        with sc2:
                            sell_price = st.number_input(
                                "賣出價格",
                                min_value=0.0,
                                value=float(price) if price else float(cost_ps),
                                step=0.01,
                            )
                        if st.form_submit_button("✅ 確認賣出", use_container_width=True, type="primary"):
                            if sell_qty > 0:
                                new_qty = qty - sell_qty
                                realized = (sell_price - cost_ps) * sell_qty
                                if new_qty <= 0:
                                    remove_profile_holding(portfolio, profile_id, ticker)
                                    st.toast(f"已全數賣出，實現損益 {realized:+,.0f}")
                                else:
                                    upsert_profile_holding(portfolio, profile_id, ticker, cost_ps, new_qty)
                                    st.toast(f"賣出 {sell_qty:,.0f} 股，實現損益 {realized:+,.0f}，剩餘 {new_qty:,.0f} 股")
                                log_transaction(portfolio, profile_id, ticker, "sell", sell_qty, sell_price, cost_ps)
                                save_portfolio(portfolio)
                                st.session_state[mode_key] = None
                                st.rerun()

                # ── 直接編輯表單 ──────────────────────────────────────────────
                elif st.session_state.get(mode_key) == "edit":
                    with st.form(key=f"edit_form_{profile_id}_{ticker}"):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            new_qty = st.number_input("持股數", min_value=0.0, value=float(qty), step=1.0, format="%.0f")
                        with ec2:
                            new_cost = st.number_input("持股均價", min_value=0.0, value=float(cost_ps), step=0.01)
                        if st.form_submit_button("💾 儲存", use_container_width=True, type="primary"):
                            if new_qty > 0:
                                upsert_profile_holding(portfolio, profile_id, ticker, new_cost, new_qty)
                            else:
                                remove_profile_holding(portfolio, profile_id, ticker)
                            save_portfolio(portfolio)
                            st.session_state[mode_key] = None
                            st.rerun()


# ── Per-profile full UI ────────────────────────────────────────────────────────

def render_profile_tab(profile_id: str):
    profile_name = get_profile_name(portfolio, profile_id)
    holdings = get_profile_holdings(portfolio, profile_id)

    # ── PIN gate ──────────────────────────────────────────────────────────────
    if not render_pin_gate(profile_id, profile_name):
        return

    # ── Add / Edit form ───────────────────────────────────────────────────────
    with st.expander("➕ 新增 / 更新持股", expanded=not holdings):
        with st.form(f"form_add_{profile_id}"):
            c1, c2, c3 = st.columns(3)
            with c1:
                ticker_input = st.text_input(
                    "股票代號",
                    placeholder="台股: 2330.TW　美股: AAPL",
                    key=f"{profile_id}_ticker",
                )
            with c2:
                cost_input = st.number_input(
                    "每股成本",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    key=f"{profile_id}_cost",
                )
            with c3:
                qty_input = st.number_input(
                    "持股數量（股）",
                    min_value=0.0,
                    step=1.0,
                    format="%.0f",
                    key=f"{profile_id}_qty",
                )

            preview = cost_input * qty_input
            if preview > 0:
                st.caption(f"總投入預覽：{preview:,.2f}")

            submitted = st.form_submit_button("儲存", type="primary")
            if submitted:
                ticker = ticker_input.strip().upper()
                if not ticker:
                    st.warning("請輸入股票代號")
                elif cost_input <= 0 or qty_input <= 0:
                    st.warning("成本與數量需大於 0")
                else:
                    upsert_profile_holding(
                        portfolio, profile_id, ticker, cost_input, qty_input
                    )
                    save_portfolio(portfolio)
                    st.success(f"{ticker} 已儲存")
                    st.rerun()

    # ── Normalize / refresh names ─────────────────────────────────────────────
    if st.button("🔄 更新報價與名稱", key=f"update_{profile_id}"):
        holdings_ref = (
            portfolio.setdefault(profile_id, {}).setdefault("holdings", {})
        )
        custom_map = get_custom_name_map(portfolio)
        migrated, unresolved = [], []

        for key in list(holdings_ref.keys()):
            if any("一" <= c <= "鿿" for c in key):
                real = custom_map.get(key) or TW_NAMES_REVERSE.get(key)
                if real and real not in holdings_ref:
                    holdings_ref[real] = holdings_ref.pop(key)
                    migrated.append(f"{key} → {real}")
                elif not real:
                    unresolved.append(key)
            elif re.match(r"^\d+[A-Z]?$", key):
                tw_key = key + ".TW"
                if tw_key not in holdings_ref:
                    holdings_ref[tw_key] = holdings_ref.pop(key)
                    migrated.append(f"{key} → {tw_key}")
                else:
                    holdings_ref.pop(key)
                    migrated.append(f"{key} 已合併至 {tw_key}")

        if migrated or unresolved:
            save_portfolio(portfolio)
        if migrated:
            st.toast("已轉換：" + "、".join(migrated))
        if unresolved:
            st.warning(
                "以下名稱找不到對應代號，請至「設定」→「自訂名稱對照」手動指定：\n"
                + "、".join(unresolved)
            )
        st.cache_data.clear()
        st.rerun()

    st.divider()

    # Re-read holdings in case form or normalize changed them
    holdings = get_profile_holdings(portfolio, profile_id)

    if not holdings:
        st.info("尚無持股紀錄，請從上方新增。")
        return

    # ── Fetch prices ──────────────────────────────────────────────────────────
    with st.spinner("載入即時價格中…"):
        prices: dict[str, float] = {}
        for t in holdings:
            info = resolve_info(t)
            if info:
                prices[t] = info["price"]

    # Split TW / US
    tw_h = {t: h for t, h in holdings.items() if is_tw_ticker(t)}
    us_h = {t: h for t, h in holdings.items() if not is_tw_ticker(t)}

    render_holdings_section(tw_h, "🇹🇼 台股明細", profile_id, prices)
    if tw_h and us_h:
        st.divider()
    render_holdings_section(us_h, "🇺🇸 美股明細", profile_id, prices)

    st.divider()

    # ── Pie charts ────────────────────────────────────────────────────────────
    st.subheader("📊 倉位分佈")

    if tw_h and us_h:
        col_a, col_b = st.columns(2)
        with col_a:
            fig = make_pie(tw_h, "🇹🇼 台股倉位分佈", "tw")
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        with col_b:
            fig = make_pie(us_h, "🇺🇸 美股倉位分佈", "us")
            if fig:
                st.plotly_chart(fig, use_container_width=True)
    elif tw_h:
        fig = make_pie(tw_h, "🇹🇼 台股倉位分佈", "tw")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    elif us_h:
        fig = make_pie(us_h, "🇺🇸 美股倉位分佈", "us")
        if fig:
            st.plotly_chart(fig, use_container_width=True)

    # ── Combined TW vs US（匯率換算）─────────────────────────────────────────
    if tw_h and us_h:
        st.divider()
        with st.spinner("載入匯率…"):
            usd_twd, fx_date = get_usd_twd_rate_detail()

        tw_total = sum(h["cost_per_share"] * h["quantity"] for h in tw_h.values())
        us_total_usd = sum(h["cost_per_share"] * h["quantity"] for h in us_h.values())
        us_total_twd = us_total_usd * usd_twd
        grand_twd = tw_total + us_total_twd

        col_left, col_right = st.columns([1, 2])

        with col_left:
            st.markdown("### 台美股總配比")
            st.caption(
                f"匯率 1 USD = NT${usd_twd:.4f}　"
                f"來源：Yahoo Finance 銀行間即期（{fx_date}）"
            )
            if grand_twd:
                st.metric(
                    "🇹🇼 台股", f"NT${tw_total:,.0f}",
                    f"{tw_total / grand_twd * 100:.1f}%",
                )
            st.metric("🇺🇸 美股 (USD)", f"${us_total_usd:,.2f}")
            if grand_twd:
                st.metric(
                    "🇺🇸 美股 (換算TWD)", f"NT${us_total_twd:,.0f}",
                    f"{us_total_twd / grand_twd * 100:.1f}%",
                )
            st.metric("合計 (TWD)", f"NT${grand_twd:,.0f}")

        with col_right:
            fig_combined = px.pie(
                names=["🇹🇼 台股 (TWD)", "🇺🇸 美股 (換算TWD)"],
                values=[tw_total, us_total_twd],
                title="台美股總倉位比例（統一折算台幣）",
                hole=0.42,
                template="plotly_dark",
                color_discrete_sequence=["#5c85d6", "#d68a5c"],
            )
            fig_combined.update_traces(textposition="outside", textinfo="label+percent")
            fig_combined.update_layout(
                height=380, margin=dict(l=10, r=10, t=50, b=10),
                paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
            )
            st.plotly_chart(fig_combined, use_container_width=True)


# ── Main ──────────────────────────────────────────────────────────────────────

st.header("💼 持倉管理")

# Hide Streamlit's "Press Enter to apply" hint and character counter globally
st.markdown(
    """<style>
    [data-testid="InputInstructions"] { display: none !important; }
    </style>""",
    unsafe_allow_html=True,
)

name_a = get_profile_name(portfolio, "profile_a")
name_b = get_profile_name(portfolio, "profile_b")

tab_a, tab_b = st.tabs([f"👤 {name_a}", f"👤 {name_b}"])

with tab_a:
    render_profile_tab("profile_a")

with tab_b:
    render_profile_tab("profile_b")
