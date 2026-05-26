from __future__ import annotations

import streamlit as st


@st.cache_data(ttl=1800, show_spinner=False)
def _call_gemini(
    api_key: str,
    ticker: str,
    name: str,
    price: float,
    change_pct: float,
    w52_low: float | None,
    w52_high: float | None,
    volume: int,
    pe_ratio: float | None,
) -> str:
    """Cached Gemini call — all args are primitives so caching works correctly."""
    try:
        from google import genai
    except ImportError:
        return "⚠️ 缺少 google-genai 套件，請確認 requirements.txt。"

    # 52-week position context
    if w52_low and w52_high and w52_high > w52_low:
        pos = (price - w52_low) / (w52_high - w52_low) * 100
        w52_str = (
            f"52週區間：{w52_low:,.2f} ～ {w52_high:,.2f}"
            f"　目前位置 {pos:.0f}%（0%=年低 / 100%=年高）"
        )
    else:
        w52_str = "52週區間：資料不足"

    pe_str = f"本益比(P/E)：{pe_ratio:.1f}" if pe_ratio else "本益比：N/A"

    prompt = (
        f"你是一位資深股市分析師，請根據以下數據，用**繁體中文**提供簡潔的買入或加碼建議"
        f"（回應限制在 200 字以內，語氣直接且有觀點，不要模糊帶過）：\n\n"
        f"股票：{name}（{ticker}）\n"
        f"今日價格：{price:,.2f}　漲跌：{change_pct:+.2f}%\n"
        f"{w52_str}\n"
        f"成交量：{volume:,}\n"
        f"{pe_str}\n\n"
        f"請依序回答：\n"
        f"1. 【技術面】目前價格在52週的位置評估（偏高？偏低？中間段？）\n"
        f"2. 【建議】現在適合買入或加碼嗎？給出明確意見\n"
        f"3. 【風險】主要風險提示 1～2 點\n\n"
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


def fetch_ai_analysis(ticker: str, info: dict) -> str:
    """Public entry-point: resolves API key then delegates to cached function."""
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

    return _call_gemini(
        api_key=api_key,
        ticker=ticker,
        name=info.get("display_name") or info.get("name", ticker),
        price=float(info.get("price") or 0),
        change_pct=float(info.get("change_pct") or 0),
        w52_low=info.get("week_52_low"),
        w52_high=info.get("week_52_high"),
        volume=int(info.get("volume") or 0),
        pe_ratio=info.get("pe_ratio"),
    )
