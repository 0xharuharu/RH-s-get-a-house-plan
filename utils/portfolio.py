from __future__ import annotations

import hashlib
import json
import os
import re as _re

_DIR = os.path.dirname(__file__)
PORTFOLIO_FILE = os.path.abspath(os.path.join(_DIR, "..", "data", "portfolio.json"))


# ── Cloud storage via GitHub Gist (optional) ──────────────────────────────────
# When deployed on Streamlit Cloud, set secrets: github_token + gist_id.
# Locally (no secrets), falls back to the local portfolio.json file.

def _gist_creds() -> tuple[str, str] | tuple[None, None]:
    """Return (token, gist_id) from st.secrets, or (None, None) for local mode."""
    try:
        import streamlit as _st
        token = _st.secrets.get("github_token", "")
        gist_id = _st.secrets.get("gist_id", "")
        if token and gist_id:
            return str(token), str(gist_id)
    except Exception:
        pass
    return None, None


def _gist_load(token: str, gist_id: str) -> dict:
    import requests as _req
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = _req.get(
        f"https://api.github.com/gists/{gist_id}",
        headers=headers,
        timeout=10,
    )
    r.raise_for_status()
    files = r.json().get("files", {})
    pf = files.get("portfolio.json", {})
    content = pf.get("content", "")
    return json.loads(content) if content else {}


def _gist_save(token: str, gist_id: str, portfolio: dict):
    import requests as _req
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "files": {
            "portfolio.json": {
                "content": json.dumps(portfolio, ensure_ascii=False, indent=2)
            }
        }
    }
    r = _req.patch(
        f"https://api.github.com/gists/{gist_id}",
        headers=headers,
        json=payload,
        timeout=10,
    )
    r.raise_for_status()

DEFAULT_PORTFOLIO: dict = {
    "tw_groups": {
        "半導體": ["2330.TW", "2454.TW", "2303.TW"],
        "電子代工": ["2317.TW", "2382.TW"],
        "金融": ["2882.TW", "2881.TW"],
        "ETF": ["0050.TW", "0056.TW"],
        "持有": [],
        "自選": [],
    },
    "us_groups": {
        "科技": ["AAPL", "MSFT", "GOOGL"],
        "半導體": ["NVDA", "AMD"],
        "ETF": ["SPY", "QQQ"],
        "持有": [],
        "自選": [],
    },
    "holdings": {},
}


def load_portfolio() -> dict:
    token, gist_id = _gist_creds()
    if token and gist_id:
        try:
            data = _gist_load(token, gist_id)
            if not data:
                data = DEFAULT_PORTFOLIO.copy()
            if "groups" in data and "tw_groups" not in data:
                data = _migrate_v1(data)
            ensure_profiles(data)
            return data
        except Exception:
            pass  # network error → fall through to local file

    # ── Local file mode (development) ─────────────────────────────────────────
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "groups" in data and "tw_groups" not in data:
            data = _migrate_v1(data)
        ensure_profiles(data)
        return data
    p = DEFAULT_PORTFOLIO.copy()
    ensure_profiles(p)
    return p


def _migrate_v1(old: dict) -> dict:
    new: dict = {
        "tw_groups": {"持有": [], "自選": []},
        "us_groups": {"持有": [], "自選": []},
        "holdings": {},
    }
    for name, tickers in old.get("groups", {}).items():
        tw = [t for t in tickers if t.endswith(".TW")]
        us = [t for t in tickers if not t.endswith(".TW")]
        if tw:
            new["tw_groups"][name] = tw
        if us:
            new["us_groups"][name] = us
    return new


def save_portfolio(portfolio: dict):
    token, gist_id = _gist_creds()
    if token and gist_id:
        try:
            _gist_save(token, gist_id, portfolio)
            return
        except Exception:
            pass  # network error → fall through to local file

    # ── Local file mode (development) ─────────────────────────────────────────
    os.makedirs(os.path.dirname(PORTFOLIO_FILE), exist_ok=True)
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)


def all_tickers(portfolio: dict, market: str) -> list[str]:
    seen: set[str] = set()
    result = []
    for tickers in portfolio.get(f"{market}_groups", {}).values():
        for t in tickers:
            if t not in seen:
                seen.add(t)
                result.append(t)
    return result


def add_to_group(portfolio: dict, ticker: str, group: str, market: str) -> bool:
    key = f"{market}_groups"
    portfolio[key].setdefault(group, [])
    if ticker not in portfolio[key][group]:
        portfolio[key][group].append(ticker)
        return True
    return False


def remove_from_group(portfolio: dict, ticker: str, group: str, market: str):
    key = f"{market}_groups"
    grp = portfolio.get(key, {}).get(group, [])
    if ticker in grp:
        grp.remove(ticker)


def get_global_watch(portfolio: dict) -> list[str]:
    return portfolio.get("global_watch", [])


def add_to_global_watch(portfolio: dict, ticker: str) -> bool:
    watch = portfolio.setdefault("global_watch", [])
    if ticker not in watch:
        watch.append(ticker)
        return True
    return False


def remove_from_global_watch(portfolio: dict, ticker: str):
    watch = portfolio.get("global_watch", [])
    if ticker in watch:
        watch.remove(ticker)


def get_custom_name_map(portfolio: dict) -> dict[str, str]:
    """Returns user-defined Chinese name → ticker mapping (highest priority)."""
    return portfolio.get("custom_name_map", {})


def set_custom_name_map_entry(portfolio: dict, chinese_name: str, ticker: str):
    portfolio.setdefault("custom_name_map", {})[chinese_name] = ticker


def remove_custom_name_map_entry(portfolio: dict, chinese_name: str):
    portfolio.get("custom_name_map", {}).pop(chinese_name, None)


def add_to_home_watch(portfolio: dict, ticker: str) -> bool:
    watch = portfolio.setdefault("home_watch", [])
    if ticker not in watch:
        watch.append(ticker)
        return True
    return False


def remove_from_home_watch(portfolio: dict, ticker: str):
    watch = portfolio.get("home_watch", [])
    if ticker in watch:
        watch.remove(ticker)


def _holding_market_group_ticker(ticker: str) -> tuple[str, str]:
    """Return (market, canonical_ticker) for syncing a holding to the 持有 group."""
    if any("一" <= c <= "鿿" for c in ticker):
        return "tw", ticker  # Chinese name — keep as-is in TW group
    if ticker.endswith(".TW") or ticker.endswith(".TWO"):
        return "tw", ticker
    if _re.match(r"^\d+[A-Z]?$", ticker):
        return "tw", ticker + ".TW"
    return "us", ticker


def sync_holdings_to_groups(portfolio: dict) -> bool:
    """Sync tw_groups/us_groups '持有' to match the union of both profiles' holdings.

    Adds tickers that are in holdings but missing from the group, and removes
    tickers that are no longer held by either profile.  Returns True if changed.
    """
    all_tickers: set[str] = set()
    for pid in ("profile_a", "profile_b"):
        all_tickers.update(portfolio.get(pid, {}).get("holdings", {}).keys())

    expected_tw: set[str] = set()
    expected_us: set[str] = set()
    for t in all_tickers:
        market, group_ticker = _holding_market_group_ticker(t)
        (expected_tw if market == "tw" else expected_us).add(group_ticker)

    changed = False
    for grp_key, expected in (("tw_groups", expected_tw), ("us_groups", expected_us)):
        lst = portfolio.setdefault(grp_key, {}).setdefault("持有", [])
        current = set(lst)
        for t in sorted(expected - current):
            lst.append(t)
            changed = True
        for t in current - expected:
            lst.remove(t)
            changed = True
    return changed


def upsert_holding(portfolio: dict, ticker: str, cost_per_share: float, quantity: float):
    portfolio.setdefault("holdings", {})[ticker] = {
        "cost_per_share": cost_per_share,
        "quantity": quantity,
    }
    market, group_ticker = _holding_market_group_ticker(ticker)
    grp_key = f"{market}_groups"
    portfolio.setdefault(grp_key, {}).setdefault("持有", [])
    if group_ticker not in portfolio[grp_key]["持有"]:
        portfolio[grp_key]["持有"].append(group_ticker)


def remove_holding(portfolio: dict, ticker: str):
    portfolio.get("holdings", {}).pop(ticker, None)
    market, group_ticker = _holding_market_group_ticker(ticker)
    grp = portfolio.get(f"{market}_groups", {}).get("持有", [])
    for t in (group_ticker, ticker):
        if t in grp:
            grp.remove(t)


# ── PIN / Profile helpers ──────────────────────────────────────────────────────

def hash_pin(pin: str) -> str:
    """Return SHA-256 hex digest of a 4-digit PIN string."""
    return hashlib.sha256(pin.encode()).hexdigest()


def verify_pin(pin: str, pin_hash: str) -> bool:
    return hash_pin(pin) == pin_hash


def ensure_profiles(portfolio: dict) -> bool:
    """Idempotent migration: copy old holdings → profile_a on first run.
    Returns True if any change was made (caller may wish to save)."""
    changed = False
    if "profile_a" not in portfolio:
        portfolio["profile_a"] = {"holdings": dict(portfolio.get("holdings", {}))}
        changed = True
    if "profile_b" not in portfolio:
        portfolio["profile_b"] = {"holdings": {}}
        changed = True
    settings = portfolio.setdefault("settings", {})
    profiles_cfg = settings.setdefault("profiles", {})
    if "profile_a" not in profiles_cfg:
        profiles_cfg["profile_a"] = {"name": "HARU", "pin_hash": None}
        changed = True
    if "profile_b" not in profiles_cfg:
        profiles_cfg["profile_b"] = {"name": "RAY", "pin_hash": None}
        changed = True
    return changed


def get_profile_name(portfolio: dict, profile_id: str) -> str:
    defaults = {"profile_a": "HARU", "profile_b": "RAY"}
    return (
        portfolio.get("settings", {})
        .get("profiles", {})
        .get(profile_id, {})
        .get("name")
        or defaults.get(profile_id, profile_id)
    )


def set_profile_name(portfolio: dict, profile_id: str, name: str):
    (
        portfolio.setdefault("settings", {})
        .setdefault("profiles", {})
        .setdefault(profile_id, {})
    )["name"] = name


def get_profile_pin_hash(portfolio: dict, profile_id: str) -> str | None:
    return (
        portfolio.get("settings", {})
        .get("profiles", {})
        .get(profile_id, {})
        .get("pin_hash")
    )


def set_profile_pin(portfolio: dict, profile_id: str, pin: str):
    (
        portfolio.setdefault("settings", {})
        .setdefault("profiles", {})
        .setdefault(profile_id, {})
    )["pin_hash"] = hash_pin(pin)


def clear_profile_pin(portfolio: dict, profile_id: str):
    cfg = (
        portfolio.setdefault("settings", {})
        .setdefault("profiles", {})
        .setdefault(profile_id, {})
    )
    cfg["pin_hash"] = None


def get_profile_holdings(portfolio: dict, profile_id: str) -> dict:
    return portfolio.get(profile_id, {}).get("holdings", {})


def upsert_profile_holding(
    portfolio: dict,
    profile_id: str,
    ticker: str,
    cost_per_share: float,
    quantity: float,
):
    profile = portfolio.setdefault(profile_id, {"holdings": {}})
    profile.setdefault("holdings", {})[ticker] = {
        "cost_per_share": cost_per_share,
        "quantity": quantity,
    }
    # Sync to tw_groups / us_groups "持有" watch-list
    market, group_ticker = _holding_market_group_ticker(ticker)
    grp_key = f"{market}_groups"
    portfolio.setdefault(grp_key, {}).setdefault("持有", [])
    if group_ticker not in portfolio[grp_key]["持有"]:
        portfolio[grp_key]["持有"].append(group_ticker)


def remove_profile_holding(portfolio: dict, profile_id: str, ticker: str):
    holdings = portfolio.get(profile_id, {}).get("holdings", {})
    holdings.pop(ticker, None)
    # Remove from 持有 group only when the other profile does not hold this ticker
    other_id = "profile_b" if profile_id == "profile_a" else "profile_a"
    other_holdings = portfolio.get(other_id, {}).get("holdings", {})
    if ticker not in other_holdings:
        market, group_ticker = _holding_market_group_ticker(ticker)
        grp = portfolio.get(f"{market}_groups", {}).get("持有", [])
        for t in (group_ticker, ticker):
            if t in grp:
                grp.remove(t)


def move_group(portfolio: dict, group_name: str, direction: int, market: str) -> bool:
    """Move a group up (direction=-1) or down (+1) within its market's group list.
    Returns True if the order changed."""
    key = f"{market}_groups"
    items = list(portfolio.get(key, {}).items())
    idx = next((i for i, (k, _) in enumerate(items) if k == group_name), None)
    if idx is None:
        return False
    new_idx = idx + direction
    if 0 <= new_idx < len(items):
        items[idx], items[new_idx] = items[new_idx], items[idx]
        portfolio[key] = dict(items)
        return True
    return False


def get_capital(portfolio: dict, profile_id: str) -> float:
    return float(portfolio.get(profile_id, {}).get("capital", 0.0))


def set_capital(portfolio: dict, profile_id: str, amount: float):
    portfolio.setdefault(profile_id, {})["capital"] = float(amount)


def get_target_pct(portfolio: dict, profile_id: str) -> float:
    return float(portfolio.get(profile_id, {}).get("target_pct", 80.0))


def set_target_pct(portfolio: dict, profile_id: str, pct: float):
    portfolio.setdefault(profile_id, {})["target_pct"] = float(pct)


def log_transaction(
    portfolio: dict,
    profile_id: str,
    ticker: str,
    action: str,          # "buy" | "sell"
    qty: float,
    price: float,
    cost_basis: float | None = None,
    date: str | None = None,
):
    """Append a transaction record. Realized P&L is computed for sells."""
    from datetime import date as _d
    if date is None:
        date = str(_d.today())
    realized_pnl = None
    if action == "sell" and cost_basis is not None:
        realized_pnl = round((price - cost_basis) * qty, 4)
    record = {
        "date": date,
        "ticker": ticker,
        "action": action,
        "qty": float(qty),
        "price": float(price),
        "cost_basis": float(cost_basis) if cost_basis is not None else None,
        "realized_pnl": realized_pnl,
    }
    portfolio.setdefault(profile_id, {}).setdefault("transactions", []).append(record)


def get_transactions(portfolio: dict, profile_id: str) -> list[dict]:
    return portfolio.get(profile_id, {}).get("transactions", [])


# ── Broker fee settings ───────────────────────────────────────────────────────

def get_broker_fee_rate(portfolio: dict) -> float:
    """Effective commission rate after broker discount.
    Default = 0.1425% × 0.6 (standard rate at 6折).
    """
    return float(portfolio.get("broker_fee_rate", 0.001425 * 0.6))


def set_broker_fee_rate(portfolio: dict, rate: float) -> None:
    portfolio["broker_fee_rate"] = rate


def calc_commission(amount: float, fee_rate: float) -> float:
    """Buy or sell commission. Minimum NT$20."""
    return max(amount * fee_rate, 20.0)


def calc_sell_tax(amount: float, is_etf: bool = False) -> float:
    """Taiwan Securities Transaction Tax: 0.3% stocks, 0.1% ETFs."""
    return amount * (0.001 if is_etf else 0.003)


def calc_sell_costs(price: float, qty: float, fee_rate: float, is_etf: bool = False) -> float:
    """Total estimated costs when selling (commission + tax). TW stocks only."""
    amount = price * qty
    return calc_commission(amount, fee_rate) + calc_sell_tax(amount, is_etf)


def calc_summary(
    portfolio: dict,
    prices: dict[str, float],
) -> tuple[list[dict], float, float]:
    holdings = portfolio.get("holdings", {})
    if not holdings:
        return [], 0.0, 0.0

    total_cost = sum(h["cost_per_share"] * h["quantity"] for h in holdings.values())

    rows = []
    for ticker, h in holdings.items():
        cost_ps = h["cost_per_share"]
        qty = h["quantity"]
        cost_total = cost_ps * qty
        price = prices.get(ticker, cost_ps)
        mkt_val = price * qty
        pnl = mkt_val - cost_total
        pnl_pct = (pnl / cost_total * 100) if cost_total else 0
        pos_pct = (cost_total / total_cost * 100) if total_cost else 0
        rows.append({
            "ticker": ticker,
            "cost_per_share": cost_ps,
            "quantity": qty,
            "total_cost": cost_total,
            "current_price": price,
            "market_value": mkt_val,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "position_pct": pos_pct,
            "is_tw": ticker.endswith(".TW"),
        })

    total_mkt = sum(r["market_value"] for r in rows)
    return rows, total_cost, total_mkt
