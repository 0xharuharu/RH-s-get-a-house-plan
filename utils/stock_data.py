from __future__ import annotations

import re
import yfinance as yf
import pandas as pd
import streamlit as st

TW_NAMES: dict[str, str] = {
    "0050.TW": "台灣50",
    "0056.TW": "元大高股息",
    "00631L.TW": "元大台灣50正2",
    "00632R.TW": "元大台灣50反1",
    "00692.TW": "富邦公司治理",
    "00713.TW": "元大台灣高息低波",
    "00720B.TW": "元大投資級公司債",
    "00878.TW": "國泰永續高股息",
    "00919.TW": "群益台灣精選高息",
    "00929.TW": "復華台灣科技優息",
    "00939.TW": "統一台灣高息動能",
    "00940.TW": "元大台灣價值高息",
    "00981A.TW": "主動統一台股增長",
    "00985B.TW": "凱基AAA至A級公司債主動",
    "00988A.TW": "主動統一全球創新",
    "1301.TW": "台塑",
    "1303.TW": "南亞",
    "1326.TW": "台化",
    "1590.TW": "亞德客-KY",
    "2002.TW": "中鋼",
    "2207.TW": "和泰車",
    "2301.TW": "光寶科",
    "2303.TW": "聯電",
    "2308.TW": "台達電",
    "2317.TW": "鴻海",
    "2324.TW": "仁寶",
    "2327.TW": "國巨",
    "2330.TW": "台積電",
    "2337.TW": "旺宏",
    "2344.TW": "華邦電",
    "2352.TW": "佳世達",
    "2353.TW": "宏碁",
    "2354.TW": "鴻準",
    "2356.TW": "英業達",
    "2357.TW": "華碩",
    "2376.TW": "技嘉",
    "2377.TW": "微星",
    "2379.TW": "瑞昱",
    "2382.TW": "廣達",
    "2385.TW": "群光",
    "2395.TW": "研華",
    "2408.TW": "南亞科",
    "2409.TW": "友達",
    "2412.TW": "中華電",
    "2454.TW": "聯發科",
    "2474.TW": "可成",
    "2603.TW": "長榮",
    "2609.TW": "陽明",
    "2615.TW": "萬海",
    "2880.TW": "華南金",
    "2881.TW": "富邦金",
    "2882.TW": "國泰金",
    "2883.TW": "開發金",
    "2884.TW": "玉山金",
    "2885.TW": "元大金",
    "2886.TW": "兆豐金",
    "2887.TW": "台新金",
    "2890.TW": "永豐金",
    "2891.TW": "中信金",
    "2892.TW": "第一金",
    "3008.TW": "大立光",
    "3034.TW": "聯詠",
    "3037.TW": "欣興",
    "3045.TW": "台灣大",
    "3481.TW": "群創",
    "3711.TW": "日月光投控",
    "4904.TW": "遠傳",
    "4938.TW": "和碩",
    "5880.TW": "合庫金",
    "6196.TW": "帆宣",
    "6274.TW": "台燿",
    "6505.TW": "台塑化",
    "6669.TW": "緯穎",
    "3105.TW": "穩懋",
    "6278.TW": "台表科",
    "6770.TW": "力積電",
    "8046.TW": "南電",
    "2492.TW": "華新科",
    "3026.TW": "禾伸堂",
    "2478.TW": "大毅",
    "6153.TW": "嘉聯益",
    # ── 上櫃 (OTC / .TWO) ──────────────────────────────────────────────────
    "3105.TWO": "穩懋",
    "8050.TWO": "廣積",
    "6488.TWO": "環球晶",
    "3533.TWO": "嘉澤",
    "6443.TWO": "元晶",
    "4966.TWO": "譜瑞-KY",
    "6239.TWO": "力成",
    "6285.TWO": "啟碁",
    "3661.TWO": "世芯-KY",
    "8069.TWO": "元太",
    "3413.TWO": "京鼎",
    "6456.TWO": "GIS-KY",
    "5274.TWO": "信驊",
    "3017.TWO": "奇鋐",
    "6510.TWO": "精測",
    "4977.TWO": "眾達-KY",
    "6679.TWO": "鈺太",
}

# 反查：中文名稱 → 代號（供持倉管理使用）
TW_NAMES_REVERSE: dict[str, str] = {v: k for k, v in TW_NAMES.items()}


def get_display_name(ticker: str, yf_name: str = "") -> str:
    return TW_NAMES.get(ticker, yf_name or ticker)


def stock_label(ticker: str, yf_name: str = "") -> str:
    if ticker.endswith(".TW") or ticker.endswith(".TWO"):
        display = TW_NAMES.get(ticker, yf_name or ticker)
        return f"{display} {ticker}"
    return f"{ticker}  {yf_name}" if yf_name else ticker


# ── TWSE MIS real-time price ──────────────────────────────────────────────────

@st.cache_data(ttl=60)
def get_twse_mis_price(ticker: str) -> dict | None:
    """Fetch live price from TWSE Market Information System (no auth needed).
    Works only for .TW (TWSE) and .TWO (Taipei Exchange / OTC) tickers.
    Returns dict with price, prev_close, change, change_pct, volume, time_str
    or None if unavailable / market closed with no data.
    Cache TTL: 60 s (intraday refresh friendly).
    """
    import requests as _req

    if ticker.endswith(".TW"):
        ex_ch = f"tse_{ticker[:-3]}.tw"
    elif ticker.endswith(".TWO"):
        ex_ch = f"otc_{ticker[:-4]}.tw"
    else:
        return None

    url = (
        "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
        f"?ex_ch={ex_ch}&json=1&delay=0"
    )
    try:
        r = _req.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        items = r.json().get("msgArray", [])
        if not items:
            return None
        item = items[0]

        z = item.get("z", "-")   # 當前成交價 (current price)
        y = item.get("y", "-")   # 昨日收盤 (previous close)

        # Market not open or pre-open: z may be "-"; fall back to prev close
        if not z or z == "-":
            z = y
        if not z or not y or z == "-" or y == "-":
            return None

        price = float(z)
        prev_close = float(y)
        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close * 100) if prev_close else 0, 4)

        try:
            # v is accumulated volume in 千股 (1 lot = 1,000 shares)
            volume = int(float(item.get("v", "0"))) * 1000
        except (ValueError, TypeError):
            volume = 0

        return {
            "price": price,
            "prev_close": prev_close,
            "change": change,
            "change_pct": change_pct,
            "volume": volume,
            "time_str": item.get("t", ""),
            "name_tw": item.get("n", ""),
        }
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_stock_info(ticker: str) -> dict | None:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="5d")

        if hist.empty:
            return None

        current_price = float(hist["Close"].iloc[-1])
        prev_price = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
        change = current_price - prev_price
        change_pct = (change / prev_price * 100) if prev_price else 0

        yf_name = info.get("longName") or info.get("shortName", ticker)
        is_tw = ticker.endswith(".TW") or ticker.endswith(".TWO")
        last_trade_date = str(hist.index[-1])[:10]

        result: dict = {
            "ticker": ticker,
            "name": yf_name,
            "display_name": get_display_name(ticker, yf_name),
            "label": stock_label(ticker, yf_name),
            "price": current_price,
            "change": change,
            "change_pct": change_pct,
            "volume": int(hist["Volume"].iloc[-1]),
            "currency": info.get("currency", "TWD" if is_tw else "USD"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            "is_tw": is_tw,
            "last_trade_date": last_trade_date,
            "data_source": "yfinance",
        }

        # TW stocks: overlay TWSE MIS live price for fresher, official numbers
        if is_tw:
            mis = get_twse_mis_price(ticker)
            if mis:
                result["price"] = mis["price"]
                result["change"] = mis["change"]
                result["change_pct"] = mis["change_pct"]
                if mis["volume"] > 0:
                    result["volume"] = mis["volume"]
                result["data_source"] = "TWSE MIS"

        return result
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_historical_data(ticker: str, period: str = "3mo") -> pd.DataFrame:
    try:
        stock = yf.Ticker(ticker)
        return stock.history(period=period, interval="1d")
    except Exception:
        return pd.DataFrame()


def format_price(value: float, is_tw: bool) -> str:
    symbol = "NT$" if is_tw else "$"
    return f"{symbol}{value:,.2f}"


def format_price_md(value: float, is_tw: bool) -> str:
    """Dollar-sign escaped for st.caption() / st.markdown() contexts."""
    symbol = r"NT\$" if is_tw else r"\$"
    return f"{symbol}{value:,.2f}"


def format_volume(volume: int) -> str:
    if volume >= 1_000_000_000:
        return f"{volume / 1_000_000_000:.1f}B"
    if volume >= 1_000_000:
        return f"{volume / 1_000_000:.1f}M"
    if volume >= 1_000:
        return f"{volume / 1_000:.1f}K"
    return str(volume)


INDEX_LABELS: dict[str, str] = {
    "^TWII":  "台股加權指數",
    "^GSPC":  "S&P 500",
    "^DJI":   "道瓊指數",
    "^IXIC":  "NASDAQ",
    "^HSI":   "恒生指數",
    "^N225":  "日經指數",
    "^VIX":   "VIX 恐慌指數",
}

TW_HOT_UNIVERSE = [
    "2330.TW", "2454.TW", "2317.TW", "2382.TW", "2303.TW",
    "2308.TW", "2379.TW", "3034.TW", "6669.TW", "3711.TW",
    "2881.TW", "2882.TW", "2884.TW", "2885.TW", "2886.TW",
    "2891.TW", "0050.TW", "0056.TW", "2603.TW", "2609.TW",
    "2357.TW", "2376.TW", "2002.TW", "3008.TW", "4938.TW",
]

US_HOT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "TSLA",
    "AMD", "AVGO", "TSM", "QCOM", "MU", "ARM",
    "JPM", "GS", "V", "MA",
    "SPY", "QQQ", "IWM",
]


@st.cache_data(ttl=3600)
def get_usd_twd_rate() -> float:
    try:
        data = yf.Ticker("USDTWD=X").history(period="2d")
        if not data.empty:
            return float(data["Close"].iloc[-1])
    except Exception:
        pass
    return 32.0  # fallback


@st.cache_data(ttl=3600)
def get_usd_twd_rate_detail() -> tuple[float, str]:
    """Returns (rate, iso_date).
    Rate source: Yahoo Finance spot FX ticker USDTWD=X (銀行間即期匯率參考).
    date is the date of the last available close (market day).
    """
    try:
        data = yf.Ticker("USDTWD=X").history(period="2d")
        if not data.empty:
            rate = float(data["Close"].iloc[-1])
            date = str(data.index[-1])[:10]
            return rate, date
    except Exception:
        pass
    return 32.0, "—"


# ── Common international stocks: Chinese name → ticker ────────────────────────
# yfinance.Search does not understand Chinese; use this static map as first-pass.
INTL_CN_NAMES: dict[str, str] = {
    # 韓國
    "海力士": "000660.KS",   "SK海力士": "000660.KS",
    "三星":   "005930.KS",   "三星電子": "005930.KS",
    "現代":   "005380.KS",   "LG電子":   "066570.KS",
    "SK電訊": "017670.KS",   "POSCO":    "005490.KS",
    "凱基":   "039490.KS",
    # 日本
    "豐田": "7203.T",   "本田": "7267.T",   "日產": "7201.T",
    "索尼": "6758.T",   "任天堂": "7974.T", "軟銀": "9984.T",
    "瑞薩": "6723.T",   "村田": "6981.T",   "信越化學": "4063.T",
    "東京電子": "8035.T", "日立": "6501.T",  "松下": "6752.T",
    "佳能": "7751.T",   "富士通": "6702.T", "夏普": "6753.T",
    "羅姆": "6963.T",   "TDK": "6762.T",
    # 香港 / 中國
    "騰訊": "0700.HK",  "阿里巴巴": "9988.HK", "美團": "3690.HK",
    "小米": "1810.HK",  "比亞迪": "1211.HK",   "京東": "9618.HK",
    "百度": "9888.HK",  "網易": "9999.HK",     "快手": "1024.HK",
    "中芯國際": "0981.HK", "華虹半導體": "1347.HK",
    "建設銀行": "0939.HK", "工商銀行": "1398.HK",
    # 美股（常見中文暱稱）
    "輝達": "NVDA",   "超微": "AMD",    "英特爾": "INTC",
    "蘋果": "AAPL",   "微軟": "MSFT",   "谷歌": "GOOGL",  "字母": "GOOGL",
    "亞馬遜": "AMZN", "特斯拉": "TSLA", "臉書": "META",   "Meta": "META",
    "波克夏": "BRK-B", "摩根大通": "JPM", "高盛": "GS",
    "輝瑞": "PFE",    "嬌生": "JNJ",    "禮來": "LLY",
    "台積電ADR": "TSM", "聯電ADR": "UMC",
    # 歐洲
    "LVMH": "MC.PA",   "愛馬仕": "RMS.PA",  "空巴": "AIR.PA",
    "SAP": "SAP.DE",   "西門子": "SIE.DE",   "寶馬": "BMW.DE",
    "賓士": "MBG.DE",  "福斯": "VOW3.DE",    "殼牌": "SHEL.L",
    "BP": "BP.L",      "阿斯特捷利康": "AZN.L", "諾華": "NOVN.SW",
}


@st.cache_data(ttl=600)
def search_tickers(query: str, max_results: int = 5) -> list[dict]:
    """Search for tickers by name/keyword.
    For Chinese input → looks up INTL_CN_NAMES first, then falls back to yfinance.
    Returns list of {symbol, name, exchange} dicts."""
    if not query or len(query.strip()) < 2:
        return []
    q = query.strip()

    # ── Chinese input: search static international name map ──────────────────
    has_cjk = any("一" <= c <= "鿿" for c in q)
    if has_cjk:
        matched: list[dict] = []
        seen: set[str] = set()
        # Exact and partial matches (query contained in key OR key contained in query)
        for cn_name, sym in INTL_CN_NAMES.items():
            if sym in seen:
                continue
            if q in cn_name or cn_name in q:
                seen.add(sym)
                matched.append({"symbol": sym, "name": cn_name, "exchange": ""})
        # Enrich names with actual yfinance English name if available
        enriched: list[dict] = []
        for m in matched[:max_results]:
            try:
                info = get_stock_info(m["symbol"])
                if info:
                    enriched.append({
                        "symbol": m["symbol"],
                        "name": f"{m['name']} ({info['name']})",
                        "exchange": m["exchange"],
                    })
                else:
                    enriched.append(m)
            except Exception:
                enriched.append(m)
        return enriched

    # ── English ticker/name: use yfinance.Search ─────────────────────────────
    try:
        result = yf.Search(q, max_results=max_results, news_count=0)
        quotes = getattr(result, "quotes", []) or []
        out = []
        for item in quotes:
            sym = item.get("symbol", "")
            name = item.get("shortname") or item.get("longname", "")
            exchange = item.get("exchange", "")
            if sym and name:
                out.append({"symbol": sym, "name": name, "exchange": exchange})
        return out
    except Exception:
        return []


@st.cache_data(ttl=600)
def get_market_movers(market: str = "tw", top_n: int = 5) -> tuple[list, list]:
    universe = TW_HOT_UNIVERSE if market == "tw" else US_HOT_UNIVERSE
    results = []
    for ticker in universe:
        info = get_stock_info(ticker)
        if info:
            results.append(info)
    if not results:
        return [], []
    ranked = sorted(results, key=lambda x: x["change_pct"], reverse=True)
    return ranked[:top_n], ranked[-top_n:][::-1]


# ── Sector definitions ────────────────────────────────────────────────────────

TW_SECTOR_GROUPS: dict[str, dict] = {
    "半導體": {
        "icon": "💾",
        "desc": "晶圓代工・IC設計・封測",
        "tickers": ["2330.TW", "2454.TW", "2303.TW", "3711.TW", "3034.TW", "2379.TW"],
    },
    "AI / 伺服器": {
        "icon": "🤖",
        "desc": "AI伺服器設計・雲端基礎設施",
        "tickers": ["6669.TW", "2382.TW", "2356.TW", "2357.TW", "2395.TW"],
    },
    "電子代工": {
        "icon": "🏭",
        "desc": "EMS 電子製造服務",
        "tickers": ["2317.TW", "2324.TW", "4938.TW"],
    },
    "PCB / 基板": {
        "icon": "🔌",
        "desc": "印刷電路板・IC載板",
        "tickers": ["3037.TW", "8046.TW", "6274.TW", "6278.TW", "6153.TW"],
    },
    "被動元件": {
        "icon": "⚡",
        "desc": "電阻・電容・電感等被動元件",
        "tickers": ["2327.TW", "2492.TW", "3026.TW", "2478.TW"],
    },
    "面板": {
        "icon": "📺",
        "desc": "LCD / OLED 顯示面板",
        "tickers": ["2409.TW", "3481.TW"],
    },
    "記憶體": {
        "icon": "💿",
        "desc": "DRAM・Flash 記憶體",
        "tickers": ["2408.TW", "2337.TW", "2344.TW", "6770.TW"],
    },
    "金融": {
        "icon": "🏦",
        "desc": "銀行・保險・金控",
        "tickers": ["2882.TW", "2881.TW", "2884.TW", "2885.TW", "2886.TW", "2891.TW"],
    },
    "航運": {
        "icon": "🚢",
        "desc": "海運・貨運",
        "tickers": ["2603.TW", "2609.TW", "2615.TW"],
    },
    "電信": {
        "icon": "📡",
        "desc": "電信服務",
        "tickers": ["2412.TW", "3045.TW", "4904.TW"],
    },
    "石化": {
        "icon": "🛢️",
        "desc": "石化・塑化",
        "tickers": ["1301.TW", "1303.TW", "1326.TW", "6505.TW"],
    },
}

US_SECTOR_GROUPS: dict[str, dict] = {
    "AI / 半導體": {
        "icon": "🤖",
        "desc": "AI晶片・半導體設計",
        "tickers": ["NVDA", "AMD", "AVGO", "QCOM", "ARM", "TSM", "MU"],
    },
    "科技巨頭": {
        "icon": "💻",
        "desc": "大型科技平台・雲端",
        "tickers": ["AAPL", "MSFT", "GOOGL", "META", "AMZN"],
    },
    "金融": {
        "icon": "🏦",
        "desc": "銀行・金融服務・支付",
        "tickers": ["JPM", "GS", "V", "MA"],
    },
}


# Maps yfinance `industry` strings → our sector group names (used for dynamic matching)
YFINANCE_TO_SECTOR: dict[str, list[str]] = {
    "Semiconductors":                         ["AI / 半導體", "半導體"],
    "Semiconductor Equipment & Materials":    ["AI / 半導體", "半導體"],
    "Consumer Electronics":                   ["科技巨頭"],
    "Internet Content & Information":         ["科技巨頭"],
    "Software—Application":                   ["科技巨頭"],
    "Software—Infrastructure":                ["科技巨頭"],
    "Computer Hardware":                      ["科技巨頭", "AI / 伺服器"],
    "Electronic Components":                  ["被動元件"],
    "Banks—Diversified":                      ["金融"],
    "Banks—Regional":                         ["金融"],
    "Capital Markets":                        ["金融"],
    "Credit Services":                        ["金融"],
    "Insurance—Life":                         ["金融"],
    "Insurance—Property & Casualty":          ["金融"],
    "Marine Shipping":                        ["航運"],
    "Telecom Services":                       ["電信"],
    "Specialty Chemicals":                    ["石化"],
    "Chemicals":                              ["石化"],
    "Communication Equipment":               ["AI / 伺服器"],
    "Electronic Gaming & Multimedia":        ["科技巨頭"],
    "Information Technology Services":       ["科技巨頭"],
}


def find_sectors_for_ticker(ticker: str) -> list[tuple[str, str, dict]]:
    """Return [(market, sector_name, meta), ...] for all sectors the ticker belongs to."""
    results = []
    for name, meta in TW_SECTOR_GROUPS.items():
        if ticker in meta["tickers"]:
            results.append(("tw", name, meta))
    for name, meta in US_SECTOR_GROUPS.items():
        if ticker in meta["tickers"]:
            results.append(("us", name, meta))
    return results


@st.cache_data(ttl=600)
def get_sector_performance(market: str = "tw") -> list[dict]:
    """Return sectors sorted by average daily change_pct (descending)."""
    groups = TW_SECTOR_GROUPS if market == "tw" else US_SECTOR_GROUPS
    results = []
    for name, meta in groups.items():
        changes: list[float] = []
        stocks_detail: list[dict] = []
        for ticker in meta["tickers"]:
            info = get_stock_info(ticker)
            if info:
                changes.append(info["change_pct"])
                stocks_detail.append({
                    "ticker": ticker,
                    "display_name": info.get("display_name", ticker),
                    "change_pct": info["change_pct"],
                    "price": info["price"],
                })
        if changes:
            avg_chg = sum(changes) / len(changes)
            results.append({
                "name": name,
                "icon": meta.get("icon", ""),
                "desc": meta.get("desc", ""),
                "avg_change_pct": avg_chg,
                "stocks": sorted(stocks_detail, key=lambda x: x["change_pct"], reverse=True),
                "n_fetched": len(changes),
            })
    return sorted(results, key=lambda x: x["avg_change_pct"], reverse=True)


@st.cache_data(ttl=300)
def get_stock_detail(ticker: str) -> dict | None:
    """Extended stock info: fundamentals, analyst data, news."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="5d")
        if hist.empty:
            return None

        current_price = float(hist["Close"].iloc[-1])
        prev_price = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
        change = current_price - prev_price
        change_pct = (change / prev_price * 100) if prev_price else 0
        yf_name = info.get("longName") or info.get("shortName", ticker)
        is_tw = ticker.endswith(".TW") or ticker.endswith(".TWO")
        last_trade_date = str(hist.index[-1])[:10]

        news: list[dict] = []
        try:
            raw_news = stock.news or []
            for article in raw_news[:10]:
                if not isinstance(article, dict):
                    continue
                # yfinance ≥0.2.55 wraps content under "content" key
                if "content" in article:
                    c = article["content"]
                    link_obj = c.get("canonicalUrl") or {}
                    provider = c.get("provider") or {}
                    raw_desc = c.get("description", "") or c.get("summary", "")
                    news.append({
                        "title": c.get("title", ""),
                        "publisher": provider.get("displayName", ""),
                        "link": link_obj.get("url", ""),
                        "time": 0,
                        "description": raw_desc,
                    })
                else:
                    raw_desc = article.get("description", "") or article.get("summary", "")
                    news.append({
                        "title": article.get("title", ""),
                        "publisher": article.get("publisher", ""),
                        "link": article.get("link", ""),
                        "time": article.get("providerPublishTime", 0),
                        "description": raw_desc,
                    })
        except Exception:
            pass

        return {
            "ticker": ticker,
            "name": yf_name,
            "display_name": get_display_name(ticker, yf_name),
            "label": stock_label(ticker, yf_name),
            "price": current_price,
            "change": change,
            "change_pct": change_pct,
            "currency": info.get("currency", "TWD" if is_tw else "USD"),
            "volume": int(hist["Volume"].iloc[-1]),
            "market_cap": info.get("marketCap"),
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            "is_tw": is_tw,
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "summary": info.get("longBusinessSummary", ""),
            "pe_trailing": info.get("trailingPE"),
            "pe_forward": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_equity": info.get("debtToEquity"),
            "revenue": info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "earnings_growth": info.get("earningsGrowth"),
            "recommendation": info.get("recommendationMean"),
            "target_price": info.get("targetMeanPrice"),
            "analyst_count": info.get("numberOfAnalystOpinions"),
            "last_trade_date": last_trade_date,
            "news": news,
        }
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_news_rss(ticker: str) -> list[dict]:
    """Fetch news: Yahoo Finance RSS → Google News RSS fallback."""
    try:
        import feedparser
        import time as _time
        import urllib.parse

        def _parse(url: str) -> list[dict]:
            try:
                feed = feedparser.parse(url)
                out = []
                for entry in (feed.entries or [])[:10]:
                    title = entry.get("title", "")
                    if not title:
                        continue
                    pub_time = 0
                    pp = entry.get("published_parsed")
                    if pp:
                        try:
                            pub_time = int(_time.mktime(pp))
                        except Exception:
                            pass
                    src = entry.get("source", {})
                    publisher = (
                        src.get("title", "") if isinstance(src, dict)
                        else entry.get("author", "")
                    )
                    raw_desc = entry.get("summary", "") or entry.get("description", "")
                    # Strip HTML tags from description
                    desc = re.sub(r"<[^>]+>", " ", raw_desc).strip() if raw_desc else ""
                    out.append({
                        "title": title,
                        "publisher": publisher,
                        "link": entry.get("link", ""),
                        "time": pub_time,
                        "description": desc,
                    })
                return out
            except Exception:
                return []

        # 1. Yahoo Finance RSS
        news = _parse(
            f"https://feeds.finance.yahoo.com/rss/2.0/headline"
            f"?s={ticker}&region=US&lang=en-US"
        )
        if news:
            return news

        # 2. Google News RSS (use Chinese name for TW tickers)
        is_tw_ticker = ticker.endswith(".TW") or ticker.endswith(".TWO")
        cn_name = TW_NAMES.get(ticker, "")
        if is_tw_ticker and cn_name:
            query = urllib.parse.quote(cn_name)
            url = (
                f"https://news.google.com/rss/search"
                f"?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            )
        else:
            base = ticker.split(".")[0]
            query = urllib.parse.quote(f"{base} stock earnings")
            url = (
                f"https://news.google.com/rss/search"
                f"?q={query}&hl=en-US&gl=US&ceid=US:en"
            )
        return _parse(url)

    except Exception:
        return []


@st.cache_data(ttl=300)
def get_news_finnhub(ticker: str, api_key: str) -> list[dict]:
    """Finnhub company news (free: 60 req/min). Best for US stocks."""
    if not api_key:
        return []
    try:
        import requests
        import datetime as _dt
        today = _dt.date.today().isoformat()
        week_ago = (_dt.date.today() - _dt.timedelta(days=7)).isoformat()
        resp = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker, "from": week_ago, "to": today, "token": api_key},
            timeout=10,
        )
        data = resp.json()
        if not isinstance(data, list):
            return []
        return [
            {
                "title": item.get("headline", ""),
                "publisher": item.get("source", ""),
                "link": item.get("url", ""),
                "time": item.get("datetime", 0),
                "description": item.get("summary", ""),
                "sentiment": "",
                "lang": "en",
            }
            for item in data[:15]
            if item.get("headline")
        ]
    except Exception:
        return []


@st.cache_data(ttl=300)
def get_news_cnyes(ticker: str) -> list[dict]:
    """鉅亨網 news (no API key needed). Best for TW stocks.
    Tries the CNYES search API first; falls back to Google News RSS."""
    if not (ticker.endswith(".TW") or ticker.endswith(".TWO")):
        return []

    cn_name = TW_NAMES.get(ticker) or TW_NAMES.get(ticker.replace(".TWO", ".TW"))
    code = ticker.replace(".TW", "").replace(".TWO", "")
    keyword = cn_name if cn_name else code

    # Noise-title patterns — these are intraday price-alert posts, not news
    _NOISE_PREFIXES = (
        "盤中速報", "即時速報", "【速報】", "【盤中速報】",
        "Intraday", "Price Alert",
    )

    def _is_noise(title: str) -> bool:
        return any(title.startswith(p) for p in _NOISE_PREFIXES)

    def _desc_is_duplicate(title: str, desc: str) -> bool:
        """True when description adds nothing beyond the title."""
        if not desc:
            return True
        # Strip common RSS suffixes like " - news.cnyes.com"
        clean = re.sub(r"\s*[-–]\s*news\.\S+$", "", desc.strip())
        # If desc starts with most of the title, it's a repeat
        prefix = title[:min(30, len(title))]
        return clean.startswith(prefix) or clean == title.strip()

    # ── Attempt 1: CNYES search API ──────────────────────────────────────────
    try:
        import requests as _req
        resp = _req.get(
            "https://api.cnyes.com/media/api/v1/search",
            params={"keyword": keyword, "limit": 15, "offset": 0},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Referer": "https://news.cnyes.com/",
                "Origin": "https://news.cnyes.com",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            items = (
                data.get("items", {}).get("data")
                or data.get("data")
                or []
            )
            news = []
            for item in items:
                title = item.get("title", "")
                if not title or _is_noise(title):
                    continue
                raw_desc = item.get("summary", "") or item.get("content", "")
                desc = raw_desc if not _desc_is_duplicate(title, raw_desc) else ""
                news.append({
                    "title": title,
                    "publisher": "鉅亨網",
                    "link": f"https://news.cnyes.com/news/id/{item.get('newsId', '')}",
                    "time": item.get("publishAt", 0),
                    "description": desc,
                    "sentiment": "",
                    "lang": "zh",
                })
                if len(news) >= 10:
                    break
            if news:
                return news
    except Exception:
        pass

    # ── Attempt 2: Google News RSS filtered to cnyes.com ────────────────────
    try:
        import feedparser, urllib.parse, time as _time
        query = urllib.parse.quote(f"{keyword} site:cnyes.com")
        url = (
            f"https://news.google.com/rss/search"
            f"?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        )
        feed = feedparser.parse(url)
        result = []
        for entry in (feed.entries or [])[:15]:
            title = entry.get("title", "")
            if not title or _is_noise(title):
                continue
            pub_time = 0
            pp = entry.get("published_parsed")
            if pp:
                try:
                    pub_time = int(_time.mktime(pp))
                except Exception:
                    pass
            raw_desc = entry.get("summary", "") or entry.get("description", "")
            raw_desc = re.sub(r"<[^>]+>", " ", raw_desc).strip() if raw_desc else ""
            desc = raw_desc if not _desc_is_duplicate(title, raw_desc) else ""
            result.append({
                "title": title,
                "publisher": "鉅亨網",
                "link": entry.get("link", ""),
                "time": pub_time,
                "description": desc,
                "sentiment": "",
                "lang": "zh",
            })
            if len(result) >= 10:
                break
        return result
    except Exception:
        return []


_TW_NEWS_DOMAINS: dict[str, str] = {
    "ec.ltn.com.tw":   "自由財經",
    "ltn.com.tw":      "自由財經",
    "money.udn.com":   "經濟日報",
    "udn.com":         "經濟日報",
    "cmoney.tw":       "CMoney",
    "moneydj.com":     "MoneyDJ",
    "ctee.com.tw":     "工商時報",
    "cna.com.tw":      "中央社",
    "cnyes.com":       "鉅亨網",
    "technews.tw":     "科技新報",
    "wealth.com.tw":   "財訊",
    "businesstoday.com.tw": "今周刊",
}

_TW_NOISE_PREFIXES = (
    "盤中速報", "即時速報", "【速報】", "【盤中速報】",
)


def _tw_extract_title_publisher(raw_title: str, src_dict: dict) -> tuple[str, str]:
    """Split 'Article title - Publisher' format used by Google News RSS."""
    publisher = ""
    title = raw_title
    # Try feedparser source dict first
    if isinstance(src_dict, dict):
        publisher = src_dict.get("title", "")
    # If still empty, parse from title suffix ("... - 自由財經")
    if not publisher and " - " in raw_title:
        parts = raw_title.rsplit(" - ", 1)
        if len(parts[1]) <= 20:  # publisher names are short
            title = parts[0].strip()
            publisher = parts[1].strip()
    return title, publisher


@st.cache_data(ttl=600)
def get_news_tw_multi(ticker: str) -> list[dict]:
    """Fetch TW stock news from multiple financial sites via Google News RSS.
    Sources: 自由財經, 經濟日報, CMoney, MoneyDJ, 工商時報, 中央社, 科技新報 …"""
    if not (ticker.endswith(".TW") or ticker.endswith(".TWO")):
        return []

    cn_name = TW_NAMES.get(ticker, "")
    code = ticker.replace(".TW", "").replace(".TWO", "")
    keyword = cn_name if cn_name else code

    _SITES = [
        "ec.ltn.com.tw",
        "money.udn.com",
        "cmoney.tw",
        "moneydj.com",
        "ctee.com.tw",
        "cna.com.tw",
        "technews.tw",
        "wealth.com.tw",
        "businesstoday.com.tw",
    ]

    def _pub_from_link(link: str) -> str:
        for domain, name in _TW_NEWS_DOMAINS.items():
            if domain in link:
                return name
        return ""

    try:
        import feedparser, urllib.parse, time as _time

        site_filter = " OR ".join(f"site:{s}" for s in _SITES)
        full_query = urllib.parse.quote(f"{keyword} ({site_filter})")
        url = (
            f"https://news.google.com/rss/search"
            f"?q={full_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        )
        feed = feedparser.parse(url)
        results: list[dict] = []
        seen: set[str] = set()

        for entry in (feed.entries or [])[:30]:
            raw_title = entry.get("title", "")
            if not raw_title:
                continue
            title, pub_from_title = _tw_extract_title_publisher(
                raw_title, entry.get("source", {})
            )
            if any(title.startswith(p) for p in _TW_NOISE_PREFIXES):
                continue
            prefix = title[:40]
            if prefix in seen:
                continue
            seen.add(prefix)

            pub_time = 0
            pp = entry.get("published_parsed")
            if pp:
                try:
                    pub_time = int(_time.mktime(pp))
                except Exception:
                    pass

            link = entry.get("link", "")
            publisher = _pub_from_link(link) or pub_from_title or "財經媒體"

            raw_desc = entry.get("summary", "") or entry.get("description", "")
            raw_desc = re.sub(r"<[^>]+>", " ", raw_desc).strip() if raw_desc else ""
            # Drop description when it's just the title repeated
            clean_desc = re.sub(r"\s*[-–]\s*\S+\.\S+$", "", raw_desc.strip())
            desc = raw_desc if (raw_desc and not clean_desc.startswith(title[:25])) else ""

            results.append({
                "title": title,
                "publisher": publisher,
                "link": link,
                "time": pub_time,
                "description": desc,
                "sentiment": "",
                "lang": "zh",
            })
            if len(results) >= 15:
                break
        return results
    except Exception:
        return []


@st.cache_data(ttl=300)
def get_news_alpha_vantage(ticker: str, api_key: str) -> list[dict]:
    """Fetch news from Alpha Vantage NEWS_SENTIMENT (free tier: 25 req/day)."""
    if not api_key:
        return []
    try:
        import requests
        import datetime as _dt

        url = (
            f"https://www.alphavantage.co/query"
            f"?function=NEWS_SENTIMENT&tickers={ticker}"
            f"&apikey={api_key}&limit=15&sort=LATEST"
        )
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if "Information" in data or "Note" in data:
            # Rate-limit hit or invalid key
            return []
        news: list[dict] = []
        for item in data.get("feed", [])[:15]:
            time_str = item.get("time_published", "")
            pub_time = 0
            if time_str:
                try:
                    dt = _dt.datetime.strptime(time_str, "%Y%m%dT%H%M%S")
                    pub_time = int(dt.timestamp())
                except Exception:
                    pass
            news.append({
                "title": item.get("title", ""),
                "publisher": item.get("source", ""),
                "link": item.get("url", ""),
                "time": pub_time,
                "description": item.get("summary", ""),
                "sentiment": item.get("overall_sentiment_label", ""),
                "lang": "en",
            })
        return news
    except Exception:
        return []


@st.cache_data(ttl=3600)
def translate_to_zh(text: str) -> str:
    """Translate English text to Traditional Chinese via Google Translate (no key needed).
    Returns empty string if text is already Chinese or on failure."""
    if not text or len(text) < 15:
        return ""
    # Skip if already Chinese (>30% CJK chars)
    cjk = sum(1 for c in text if "一" <= c <= "鿿")
    if cjk / len(text) > 0.3:
        return ""
    try:
        import requests as _req
        resp = _req.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx",
                "sl": "auto",
                "tl": "zh-TW",
                "dt": "t",
                "q": text[:500],
            },
            timeout=6,
        )
        parts = resp.json()
        translated = "".join(seg[0] for seg in parts[0] if seg[0]).strip()
        return translated if translated != text else ""
    except Exception:
        return ""
