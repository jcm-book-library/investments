import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch_prices as fp  # noqa: E402

AEST = 36000  # Sydney offset Yahoo reports in winter


def ts(date):
    """Yahoo stamps ASX bars at 10am Sydney time, i.e. midnight UTC."""
    return int(dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc).timestamp())


def chart(rows, divs=(), name="Vanguard Australian Shares Index ETF"):
    return {"chart": {"error": None, "result": [{
        "meta": {"currency": "AUD", "longName": name, "gmtoffset": AEST, "fullExchangeName": "ASX"},
        "timestamp": [ts(d) for d, _ in rows],
        "indicators": {"quote": [{"close": [c for _, c in rows]}]},
        "events": {"dividends": {str(ts(d)): {"amount": a, "date": ts(d)} for d, a in divs}},
    }]}}


class ParseTest(unittest.TestCase):
    def test_dates_use_exchange_time_and_nulls_dropped(self):
        p = fp.parse_chart(chart([("2026-07-01", 100.0), ("2026-07-02", None), ("2026-07-03", 101.123456)],
                                 divs=[("2026-07-01", 0.85)]))
        self.assertEqual(p["closes"], {"2026-07-01": 100.0, "2026-07-03": 101.1235})
        self.assertEqual(p["dividends"], {"2026-07-01": 0.85})
        self.assertEqual(p["currency"], "AUD")

    def test_chart_error_raises(self):
        with self.assertRaises(RuntimeError):
            fp.parse_chart({"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found"}}})

    def test_symbols(self):
        self.assertEqual(fp.yahoo_symbol("VAS"), "VAS.AX")
        self.assertEqual(fp.yahoo_symbol("^AXJO"), "^AXJO")
        self.assertEqual(fp.yahoo_symbol("AUDUSD=X"), "AUDUSD=X")


class MergeAndSummaryTest(unittest.TestCase):
    def test_fresh_values_win_and_old_dates_kept(self):
        merged = fp.merge([["2020-01-02", 80.0], ["2020-01-03", 81.0]], {"2020-01-03": 81.5, "2020-01-06": 82.0})
        self.assertEqual(merged, [["2020-01-02", 80.0], ["2020-01-03", 81.5], ["2020-01-06", 82.0]])

    def test_summary_returns_and_yield(self):
        closes = [["2025-06-30", 100.0], ["2025-12-31", 105.0], ["2026-06-29", 108.0], ["2026-06-30", 110.0]]
        s = fp.summarise(closes, [["2025-09-01", 2.0], ["2026-03-01", 2.4]])
        self.assertAlmostEqual(s["perf"]["1D"], 110 / 108 - 1, places=4)
        self.assertAlmostEqual(s["perf"]["1Y"], 0.1, places=4)
        self.assertNotIn("5Y", s["perf"])
        self.assertAlmostEqual(s["yield12m"], 4.4 / 110, places=4)
        self.assertEqual(s["spark"][-1], 110.0)


class RunTest(unittest.TestCase):
    def test_failed_fetch_keeps_stored_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            cfg = tmp / "tickers.toml"
            cfg.write_text('[[ticker]]\ncode = "VAS"\n[[ticker]]\ncode = "NOPE"\n', encoding="utf-8")
            (tmp / "prices").mkdir()
            (tmp / "prices" / "VAS.json").write_text(json.dumps(
                {"code": "VAS", "name": "Old name", "closes": [["2026-06-30", 99.0]], "dividends": []}))

            def fake(symbol, start):
                if symbol == "NOPE.AX":
                    raise RuntimeError("HTTP 404")
                return chart([("2026-07-01", 100.0)])

            index = fp.run(cfg, fetch=fake, data_dir=tmp, pause=0)
            self.assertEqual(index["errors"], {"NOPE": "HTTP 404"})
            vas = json.loads((tmp / "prices" / "VAS.json").read_text())
            self.assertEqual(vas["closes"], [["2026-06-30", 99.0], ["2026-07-01", 100.0]])
            self.assertEqual(index["tickers"]["VAS"]["last"], 100.0)
            self.assertTrue((tmp / "index.json").exists())

    def test_fresh_dividends_replace_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            cfg = tmp / "tickers.toml"
            cfg.write_text('[[ticker]]\ncode = "VAS"\n', encoding="utf-8")
            (tmp / "prices").mkdir()
            (tmp / "prices" / "VAS.json").write_text(json.dumps(
                {"code": "VAS", "closes": [["2026-06-30", 99.0]], "dividends": [["2026-06-01", 0.5]]}))
            fp.run(cfg, fetch=lambda s, st: chart([("2026-07-01", 100.0)], divs=[("2026-06-02", 0.6)]), data_dir=tmp, pause=0)
            vas = json.loads((tmp / "prices" / "VAS.json").read_text())
            self.assertEqual(vas["dividends"], [["2026-06-02", 0.6]])

    def test_repo_config_loads(self):
        start, items = fp.load_config()
        codes = [i["code"] for i in items]
        self.assertIn("VAS", codes)
        self.assertIn("ASX200", codes)
        self.assertEqual(len(codes), len(set(codes)), "duplicate ticker in tickers.toml")


if __name__ == "__main__":
    unittest.main()
