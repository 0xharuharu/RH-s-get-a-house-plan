from __future__ import annotations

import feedparser
import urllib.parse
import streamlit as st


@st.cache_data(ttl=600)
def get_stock_news(ticker: str, max_items: int = 10) -> list[dict]:
    is_tw = ticker.endswith(".TW")
    ticker_clean = ticker.replace(".TW", "")

    if is_tw:
        query = f"{ticker_clean} 股票"
        url = (
            f"https://news.google.com/rss/search"
            f"?q={urllib.parse.quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        )
    else:
        query = f"{ticker} stock"
        url = (
            f"https://news.google.com/rss/search"
            f"?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
        )

    try:
        feed = feedparser.parse(url)
        news = []
        for entry in feed.entries[:max_items]:
            news.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", "")[:16],
                "source": entry.get("source", {}).get("title", ""),
                "summary": entry.get("summary", ""),
            })
        return news
    except Exception:
        return []
