"""Free, bounded news/market collection. No model API or private credentials."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import html
import json
import math
import re
import urllib.request
from urllib.parse import quote, urlparse
import xml.etree.ElementTree as ET

CST = timezone(timedelta(hours=8))
SOURCES = [
    ("财联社", "中国财经", "newsnow", "https://newsnow.busiyi.world/api/s?id=cls-telegraph"),
    ("华尔街见闻", "中国财经", "newsnow", "https://newsnow.busiyi.world/api/s?id=wallstreetcn-quick"),
    ("金十数据", "中国财经", "newsnow", "https://newsnow.busiyi.world/api/s?id=jin10"),
    ("中新网财经", "中国财经", "rss", "https://www.chinanews.com.cn/rss/finance.xml"),
    ("中新网国际", "世界要闻", "rss", "https://www.chinanews.com.cn/rss/world.xml"),
    ("BBC World", "世界要闻", "rss", "https://feeds.bbci.co.uk/news/world/rss.xml"),
]
MARKETS = [
    ("上证指数", "000001.SS", "点"), ("恒生指数", "^HSI", "点"),
    ("纳斯达克综合", "^IXIC", "点"), ("黄金期货", "GC=F", "美元/盎司"),
    ("白银期货", "SI=F", "美元/盎司"), ("WTI 原油期货", "CL=F", "美元/桶"),
]


def iso(value):
    return value.astimezone(CST).isoformat(timespec="seconds")


def timestamp(value):
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            number = float(value)
            return datetime.fromtimestamp(number / 1000 if number > 1e11 else number, CST)
        if isinstance(value, str) and value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                parsed = parsedate_to_datetime(value)
            # Undated or timezone-less strings cannot prove a publication time.
            return parsed.astimezone(CST) if parsed.tzinfo else None
    except (ValueError, TypeError, OverflowError, OSError):
        pass
    return None


def clean(value, limit=500):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", str(value or "")))).strip()[:limit]


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 FinanceBrief/1.0", "Accept": "application/json,application/xml,text/xml,*/*"})
    with urllib.request.urlopen(request, timeout=15) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("response too large")
    return data


def parse_news(data, kind):
    if kind == "newsnow":
        return json.loads(data).get("items", [])
    root = ET.fromstring(data)
    return [{"title": item.findtext("title"), "url": item.findtext("link"),
             "pubDate": item.findtext("pubDate"), "description": item.findtext("description")}
            for item in root.findall(".//item")]


def collect_source(source, now):
    name, category, kind, url = source
    health = {"name": name, "url": url, "via": "NewsNow" if kind == "newsnow" else "官方 RSS", "checked_at": iso(now)}
    try:
        raw = parse_news(fetch(url), kind)
        items, unknown = [], 0
        for item in raw[:100]:
            extra = item.get("extra") or {}
            date = timestamp(item.get("pubDate") or (extra.get("date") if isinstance(extra, dict) else None))
            if date is None:
                unknown += 1
                continue
            if not now - timedelta(hours=24) <= date <= now:
                continue
            title, link = clean(item.get("title"), 240), str(item.get("url") or "")
            if not title or urlparse(link).scheme not in ("http", "https"):
                continue
            item_category = category
            if category == "中国财经" and re.search(r"美国|美联储|美债|美元|美股|英国|欧洲|欧盟|欧元|伊朗|以色列|沙特|乌克兰|俄罗斯|韩国|日本|纳斯达克|国际油价|国际金价", title) and not re.search(r"中国|我国|国务院|央行|人民币|A股|港股|香港", title):
                item_category = "世界要闻"
            items.append({"id": hashlib.sha256(link.encode()).hexdigest()[:16], "title": title,
                          "url": link, "source": name, "category": item_category,
                          "published_at": iso(date), "fetched_at": iso(now),
                          "summary": clean(item.get("description"), 300)})
        health.update(status="ok" if items else "empty", count=len(items), excluded_unknown_time=unknown)
        return items, health
    except Exception as exc:
        health.update(status="error", count=0, error=type(exc).__name__)
        return [], health


def deduplicate(items):
    seen, result = set(), []
    for item in sorted(items, key=lambda item: item["published_at"], reverse=True):
        title_key = re.sub(r"[\W_]", "", item["title"].lower())
        url_key = item["url"].split("#")[0]
        if title_key in seen or url_key in seen:
            continue
        seen.update((title_key, url_key))
        result.append(item)
    return result[:120]


def market_data(market, now):
    name, symbol, unit = market
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}?interval=1d&range=1mo"
    result = {"name": name, "symbol": symbol, "unit": unit, "source": "Yahoo Finance", "url": f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/", "checked_at": iso(now)}
    try:
        chart = json.loads(fetch(url))["chart"]["result"][0]
        meta = chart["meta"]
        price = meta.get("regularMarketPrice")
        if not isinstance(price, (int, float)) or not math.isfinite(price):
            raise ValueError("missing price")
        times = chart.get("timestamp", [])
        closes = chart["indicators"]["quote"][0]["close"]
        history = [{"time": iso(timestamp(t)), "close": v} for t, v in zip(times, closes) if isinstance(v, (int, float)) and math.isfinite(v)]
        quote_time = timestamp(meta.get("regularMarketTime"))
        if quote_time is None:
            raise ValueError("missing quote timestamp")
        # Use a completed earlier trading date, not the range's first close.
        trading_date = datetime.fromtimestamp(meta["regularMarketTime"], timezone(timedelta(seconds=meta.get("gmtoffset", 0)))).date()
        prior = [v for t, v in zip(times, closes) if isinstance(v, (int, float)) and math.isfinite(v) and datetime.fromtimestamp(t, timezone(timedelta(seconds=meta.get("gmtoffset", 0)))).date() < trading_date]
        previous = meta.get("previousClose") or (prior[-1] if prior else None)
        result.update(status="ok", price=price, change_pct=(price / previous - 1) * 100 if previous else None,
                      currency=meta.get("currency"), quoted_at=iso(quote_time), history=history,
                      five_day_pct=(price / prior[-5] - 1) * 100 if len(prior) >= 5 and prior[-5] else None,
                      note="延迟报价；非交易时段为最近报价。期货为供应商连续近月口径，换月可能影响走势。" if "=F" in symbol else "延迟报价；非交易时段为最近报价。")
    except Exception as exc:
        result.update(status="error", price=None, history=[], error=type(exc).__name__)
    return result


def collect(now=None):
    now = now or datetime.now(CST)
    with ThreadPoolExecutor(max_workers=6) as pool:
        batches = list(pool.map(lambda source: collect_source(source, now), SOURCES))
        markets = list(pool.map(lambda market: market_data(market, now), MARKETS))
    items = deduplicate([item for batch, _ in batches for item in batch])
    return {"generated_at": iso(now), "window_hours": 24, "refresh_minutes": 30,
            "news": items, "sources": [health for _, health in batches], "markets": markets,
            "ai_status": "基础新闻版：未调用外部 AI；AI 分析仅在当期审核文件存在时提供。"}
