# Compound

My investment watchlist, ETF price history, holdings and learning notes. It's a separate job from the budget app. If the two merge later, both read Google Sheets, so they can share a sheet.

- **Live site:** https://jcm-book-library.github.io/investments/
- **My data:** my investments Google Sheet (private, in my Drive; ID set as `DEFAULT_SHEET` in `index.html`), with these tabs:
  - **Watchlist:** Code, Name, Category, Ethical, Status, Target price, Notes, Added
  - **Purchases:** Date, Code, Type (Buy/Sell), Units, Price, Fees, Platform, Notes
  - **Resources:** Title, URL, Category, Notes

  The app creates any missing tab the first time it connects.
- **Prices:** downloaded from Yahoo Finance each weekday at about 6:20pm Melbourne time and saved in `data/`. The history builds up in the repo, so it's kept even if Yahoo drops old data.

Nothing personal goes in this repo. Only tickers and public prices are stored here, which is why it can be public for GitHub Pages.

## What's in the app
| Tab | What it does |
|---|---|
| Overview | Portfolio value, gain, estimated distributions, ASX 200 and S&P 500, and the watchlist's biggest movers |
| Watchlist | Every fund with status, notes, ethical flag, target price, 1M/1Y/5Y returns, yield and a one-year sparkline |
| Charts | Price, or growth of $10,000 with distributions reinvested. Compare up to four lines. Your buys and sells show as ▲/▼ with your average cost. Stats: total return, per-year return, biggest fall and volatility |
| Holdings | Value, cost base, gain by fund, mix by category, parcels with days held (shows when a parcel passes 12 months for the CGT discount), realised gains by financial year |
| Learn | How the market, ETFs, distributions, risk, costs, CGT and super work, a regular-investing simulator using real history, and a compound-growth calculator |
| Resources | Links from the coaching email, editable in the sheet |

## Files
| File | What it is |
|---|---|
| `index.html` | The whole app |
| `tickers.toml` | Which tickers get prices downloaded. **Add a ticker here** to chart it |
| `fetch_prices.py` | The price downloader |
| `tests/` | Tests for the downloader (`python3 -m unittest discover -s tests`) |
| `.github/workflows/prices.yml` | Runs the tests, downloads prices, commits them and publishes the site |

## One-time setup
1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. **Actions → Update prices → Run workflow** for the first price download (about a minute). After that it runs by itself.
3. Open the site and press **Connect**. It uses the same Google OAuth Client ID as Jackets & Manuscripts (same `jcm-book-library.github.io` origin), so if you've signed in to that app in this browser, it's already set.

## Adding an investment
1. In the app, go to **Watchlist → + Add**. This saves it to your sheet.
2. If it says "no data", add the code to `tickers.toml` (the app links straight to the edit page) and commit. The workflow runs on that push and downloads its full history.

Not financial advice. It's for tracking and learning.
