import os
import requests
from datetime import datetime, timedelta

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
NEWS_BASE = "https://newsapi.org/v2/everything"


def get_financial_news(query: str = "stock market Taiwan", days: int = 3, page_size: int = 10) -> list[dict]:
    if not NEWS_API_KEY:
        return _get_fallback_news()
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {
        "q": query,
        "from": from_date,
        "sortBy": "publishedAt",
        "pageSize": page_size,
        "language": "en",
        "apiKey": NEWS_API_KEY,
    }
    try:
        r = requests.get(NEWS_BASE, params=params, timeout=10)
        articles = r.json().get("articles", [])
        return [
            {
                "title": a.get("title", ""),
                "source": a.get("source", {}).get("name", ""),
                "url": a.get("url", ""),
                "published": a.get("publishedAt", "")[:10],
                "description": a.get("description", ""),
            }
            for a in articles
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]
    except Exception as e:
        print(f"[NewsAPI] 失敗: {e}")
        return []


def _get_fallback_news() -> list[dict]:
    """NewsAPI 未設定時，從 Yahoo Finance RSS 抓取"""
    import xml.etree.ElementTree as ET
    url = "https://finance.yahoo.com/news/rssindex"
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:10]
        return [
            {
                "title": i.findtext("title", ""),
                "source": "Yahoo Finance",
                "url": i.findtext("link", ""),
                "published": i.findtext("pubDate", "")[:16],
                "description": i.findtext("description", ""),
            }
            for i in items
        ]
    except Exception:
        return []
