"""Download daily closing prices and distributions for every ticker in tickers.toml.

Writes data/prices/<CODE>.json (full history) and data/index.json (latest price,
returns and a small sparkline for each ticker). History already in the repo is
kept: each run re-downloads from `history_from`, and the fresh numbers replace
the stored ones date by date, so dates Yahoo drops are never lost.

Run from the repo root:  python3 fetch_prices.py
"""
import datetime as dt
import json
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CHART_URL = ("https://query{host}.finance.yahoo.com/v8/finance/chart/{symbol}"
             "?period1={start}&period2={end}&interval=1d&events=div%2Csplit")
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
           "Accept": "application/json"}
# Calendar days back for each return window shown in the app.
PERIODS = {"1M": 30, "6M": 182, "1Y": 365, "3Y": 365 * 3, "5Y": 365 * 5, "10Y": 3652}


def load_config(path=ROOT / "tickers.toml"):
    cfg = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    items = []
    for kind in ("ticker", "benchmark"):
        for t in cfg.get(kind, []):
            code = t["code"].strip().upper()
            items.append({
                "code": code,
                "symbol": t.get("yahoo") or yahoo_symbol(code),
                "name": t.get("name", ""),
                "category": t.get("category", "Benchmark" if kind == "benchmark" else ""),
                "ethical": bool(t.get("ethical", False)),
                "benchmark": kind == "benchmark",
            })
    return cfg.get("history_from", "2000-01-01"), items


def yahoo_symbol(code):
    """ASX codes get .AX; anything already shaped like a Yahoo symbol is left alone."""
    return code if any(ch in code for ch in ".^=") else code + ".AX"


def fetch_chart(symbol, start):
    """Return Yahoo's chart JSON for symbol, trying both API hosts with a short backoff."""
    p1 = int(dt.datetime.fromisoformat(start).replace(tzinfo=dt.timezone.utc).timestamp())
    p2 = int(time.time()) + 86400
    last = None
    for attempt, host in enumerate((1, 2, 1, 2)):
        url = CHART_URL.format(host=host, symbol=urllib.request.quote(symbol), start=p1, end=p2)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code == 404:
                break  # unknown symbol: retrying won't help
        except Exception as e:  # network errors, timeouts, bad JSON
            last = str(e) or e.__class__.__name__
        time.sleep(2 ** attempt)
    raise RuntimeError(last or "no response")


def parse_chart(payload):
    """Turn Yahoo's chart JSON into {name, currency, exchange, closes, dividends}.

    Dates are the exchange's local trading date (Yahoo timestamps are UTC, so the
    exchange's gmtoffset is added before taking the date)."""
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise RuntimeError(chart["error"].get("description") or chart["error"].get("code") or "chart error")
    result = (chart.get("result") or [None])[0]
    if not result:
        raise RuntimeError("no data returned")
    meta = result.get("meta", {})
    offset = meta.get("gmtoffset", 0) or 0

    def day(ts):
        return dt.datetime.fromtimestamp(ts + offset, dt.timezone.utc).date().isoformat()

    closes = {}
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    for ts, c in zip(result.get("timestamp") or [], quote.get("close") or []):
        if c is not None and c > 0:
            closes[day(ts)] = round(float(c), 4)
    divs = {}
    for d in ((result.get("events") or {}).get("dividends") or {}).values():
        if d.get("amount"):
            divs[day(d["date"])] = round(float(d["amount"]), 6)
    return {
        "name": meta.get("longName") or meta.get("shortName") or "",
        "currency": meta.get("currency") or "",
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName") or "",
        "closes": closes,
        "dividends": divs,
    }


def merge(old_pairs, new_map):
    """Merge stored [[date, value], ...] with fresh {date: value}; fresh wins. Sorted by date."""
    merged = {d: v for d, v in (old_pairs or [])}
    merged.update(new_map)
    return [[d, merged[d]] for d in sorted(merged)]


def value_on_or_before(closes, date):
    """Close on the last trading day on or before date (closes sorted ascending)."""
    lo, hi, best = 0, len(closes) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if closes[mid][0] <= date:
            best, lo = closes[mid], mid + 1
        else:
            hi = mid - 1
    return best


def summarise(closes, dividends):
    """Latest price, day change, period returns, trailing-year yield and a sparkline."""
    if not closes:
        return {}
    last_date, last = closes[-1]
    end = dt.date.fromisoformat(last_date)
    out = {"last": last, "lastDate": last_date, "firstDate": closes[0][0], "perf": {}}
    if len(closes) > 1:
        out["perf"]["1D"] = round(last / closes[-2][1] - 1, 5)
    for label, days in PERIODS.items():
        target = (end - dt.timedelta(days=days)).isoformat()
        if target < closes[0][0]:
            continue
        base = value_on_or_before(closes, target)
        if base:
            out["perf"][label] = round(last / base[1] - 1, 5)
    year_ago = (end - dt.timedelta(days=365)).isoformat()
    paid = sum(a for d, a in dividends if d > year_ago)
    out["yield12m"] = round(paid / last, 5) if paid else 0
    # ~1 year of weekly points for the watchlist sparkline
    recent = [c for c in closes if c[0] > year_ago]
    out["spark"] = [round(c[1], 3) for c in recent[::5]] + ([recent[-1][1]] if recent and (len(recent) - 1) % 5 else [])
    return out


def run(config_path=ROOT / "tickers.toml", fetch=fetch_chart, today=None, data_dir=DATA, pause=0.5):
    start, items = load_config(config_path)
    prices = Path(data_dir) / "prices"
    prices.mkdir(parents=True, exist_ok=True)
    index = {"updated": (today or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="minutes"),
             "tickers": {}, "errors": {}}
    for it in items:
        path = prices / f"{it['code']}.json"
        stored = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        try:
            fresh = parse_chart(fetch(it["symbol"], start))
            record = {
                "code": it["code"], "symbol": it["symbol"],
                "name": fresh["name"] or stored.get("name") or it["name"],
                "currency": fresh["currency"] or stored.get("currency", ""),
                "exchange": fresh["exchange"] or stored.get("exchange", ""),
                "closes": merge(stored.get("closes"), fresh["closes"]),
                # a fresh set replaces the stored one, so dividends Yahoo has since corrected don't linger
                "dividends": [[d, a] for d, a in sorted(fresh["dividends"].items())] if fresh["dividends"] else stored.get("dividends", []),
            }
            path.write_text(json.dumps(record, separators=(",", ":")), encoding="utf-8")
            print(f"{it['code']:7} {len(record['closes']):5} days  last {record['closes'][-1] if record['closes'] else '-'}")
        except Exception as e:
            index["errors"][it["code"]] = str(e)
            print(f"{it['code']:7} FAILED: {e}", file=sys.stderr)
            record = stored
        if not record.get("closes"):
            continue
        index["tickers"][it["code"]] = {
            "name": record.get("name") or it["name"], "hint": it["name"],
            "category": it["category"], "ethical": it["ethical"], "benchmark": it["benchmark"],
            "currency": record.get("currency", ""), "symbol": it["symbol"],
            **summarise(record["closes"], record.get("dividends", [])),
        }
        time.sleep(pause)
    (Path(data_dir) / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(f"\n{len(index['tickers'])} tickers saved, {len(index['errors'])} failed")
    return index


if __name__ == "__main__":
    result = run()
    # Fail the job only if nothing at all could be fetched (e.g. Yahoo blocked us)
    if result["errors"] and len(result["errors"]) == len(load_config()[1]):
        sys.exit(1)
