from __future__ import annotations

import streamlit as st


# ── TWSE 法人買賣超 ────────────────────────────────────────────────────────────

def _fetch_tw_institutional(stock_no: str) -> str:
    """Fetch 三大法人買賣超 from TWSE T86 (last available trading day)."""
    import requests
    import datetime

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    today = datetime.date.today()

    for days_back in range(7):
        date = today - datetime.timedelta(days=days_back)
        if date.weekday() >= 5:          # skip Saturday / Sunday
            continue
        date_str = date.strftime("%Y%m%d")
        try:
            url = (
                "https://www.twse.com.tw/fund/T86"
                f"?response=json&date={date_str}&selectType=ALLBUT0999"
            )
            resp = requests.get(url, timeout=8, headers=headers)
            if resp.status_code != 200:
                continue
            data = resp.json()
            if data.get("stat") != "OK" or not data.get("data"):
                continue

            fields = data.get("fields", [])

            def _col_val(row: list, keyword: str):
                for i, f in enumerate(fields):
                    if keyword in f and i < len(row):
                        return row[i]
                return None

            def _fmt(raw, label: str):
                if raw is None:
                    return None
                try:
                    n = int(raw.replace(",", "")) // 1000   # shares → 張
                    sign = "+" if n >= 0 else ""
                    return f"{label} {sign}{n:,}張"
                except Exception:
                    return None

            for row in data["data"]:
                if not row or row[0].strip() != stock_no:
                    continue
                parts = [
                    _fmt(_col_val(row, "外陸資買賣超"), "外資"),
                    _fmt(_col_val(row, "投信買賣超"),   "投信"),
                    _fmt(_col_val(row, "自營商買賣超股數"), "自營"),
                    _fmt(_col_val(row, "三大法人"),     "合計"),
                ]
                parts = [p for p in parts if p]
                if parts:
                    d = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
                    return "　".join(parts) + f"（{d}）"
            break   # valid response but stock not in list → probably OTC
        except Exception:
            continue

    return ""


# ── Extra market data (MA + news + institutional) ─────────────────────────────

@st.cache_data(ttl=900, show_spinner=False)
def _get_extra_data(ticker: str) -> tuple[str, str, str]:
    """Return (ma_str, news_str, inst_str) — plain strings for cache safety."""
    import yfinance as yf

    ma_str   = "MA 資料不足"
    news_str  = ""
    inst_str  = ""

    # ── MA 30 / 60 / 200 ──────────────────────────────────────
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if not hist.empty and len(hist) >= 30:
            price = hist["Close"].iloc[-1]
            parts = []
            for period in [30, 60, 200]:
                if len(hist) >= period:
                    ma = hist["Close"].rolling(period).mean().iloc[-1]
                    rel = "↑高於" if price > ma else "↓低於"
                    parts.append(f"MA{period} {ma:.2f}（{rel}）")
            ma_str = "　".join(parts) if parts else "MA 資料不足"
    except Exception:
        pass

    # ── Recent news ────────────────────────────────────────────
    try:
        raw_news = yf.Ticker(ticker).news or []
        headlines = []
        for item in raw_news[:5]:
            # yfinance ≥0.2 nests title under "content"
            title = (item.get("content") or {}).get("title") or item.get("title", "")
            if title:
                headlines.append(title)
        news_str = "；".join(headlines[:3])
    except Exception:
        pass

    # ── 法人買賣超 (TWSE .TW only) ────────────────────────────
    if ticker.upper().endswith(".TW"):
        stock_no = ticker.split(".")[0]
        inst_str = _fetch_tw_institutional(stock_no)

    return ma_str, news_str, inst_str


# ── Gemini call (all primitive args → cacheable) ──────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _call_gemini(
    api_key: str,
    ticker: str,
    name: str,
    price: float,
    change_pct: float,
    volume: int,
    ma_str: str,
    news_str: str,
    inst_str: str,
) -> str:
    """Cached Gemini call — all args are primitives so caching works correctly."""
    try:
        from google import genai
    except ImportError:
        return "⚠️ 缺少 google-genai 套件，請確認 requirements.txt。"

    inst_line = f"法人買賣超：{inst_str}\n" if inst_str else "法人資料：N/A\n"
    news_line = f"近期新聞：{news_str}\n" if news_str else ""

    prompt = (
        f"你是一位資深股市分析師，請根據以下數據，用**繁體中文**提供簡潔的買入或加碼建議"
        f"（回應限制在 250 字以內，語氣直接且有觀點，不要模糊帶過）：\n\n"
        f"股票：{name}（{ticker}）\n"
        f"今日價格：{price:,.2f}　漲跌：{change_pct:+.2f}%\n"
        f"均線位置：{ma_str}\n"
        f"成交量：{volume:,}\n"
        f"{inst_line}"
        f"{news_line}"
        f"\n請依序回答：\n"
        f"1. 【技術面】均線多空排列與趨勢方向（多頭/空頭/盤整）\n"
        f"2. 【籌碼面】法人動向解讀（外資/投信/自營是否積極買超或賣超）\n"
        f"3. 【建議】現在適合買入或加碼嗎？給出明確意見與簡短理由\n"
        f"4. 【風險】主要風險提示 1～2 點\n\n"
        f"最後附上一行：「⚠️ 以上為 AI 參考分析，不構成投資建議，請自行判斷風險。」"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"⚠️ 分析失敗：{e}"


# ── Public entry-point ────────────────────────────────────────────────────────

def fetch_ai_analysis(ticker: str, info: dict) -> str:
    """Resolve API key, fetch extra market data, then call Gemini."""
    try:
        api_key = str(st.secrets.get("gemini_api_key", ""))
    except Exception:
        api_key = ""

    if not api_key:
        return (
            "⚠️ 尚未設定 Gemini API 金鑰。\n"
            "請在 Streamlit Secrets 新增：\n"
            "`gemini_api_key = \"AIza...\"`"
        )

    ma_str, news_str, inst_str = _get_extra_data(ticker)

    return _call_gemini(
        api_key=api_key,
        ticker=ticker,
        name=info.get("display_name") or info.get("name", ticker),
        price=float(info.get("price") or 0),
        change_pct=float(info.get("change_pct") or 0),
        volume=int(info.get("volume") or 0),
        ma_str=ma_str,
        news_str=news_str,
        inst_str=inst_str,
    )
