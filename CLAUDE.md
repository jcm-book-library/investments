# Compound: notes for Claude

**Read the house rules first:** [HOUSE-RULES.md](https://github.com/jcm-book-library/control-room/blob/main/HOUSE-RULES.md) in `control-room` (plain text: https://raw.githubusercontent.com/jcm-book-library/control-room/main/HOUSE-RULES.md). They cover Google Sheet safety, branches and pull requests into `main`, using cheaper models to save usage credits, and the build template. The notes below are this repo's own; where they are more specific, they win. The project charter is `project.json`.

## This repo
- `index.html` is the whole app.
- Data lives in a private investments Google Sheet (ID set as `DEFAULT_SHEET` in `index.html`, tabs Watchlist, Purchases, Resources); "Nothing personal goes in this repo."
- Prices are saved in `data/`; add a ticker to `tickers.toml` to chart it. `fetch_prices.py` is the downloader.
- GitHub Action `.github/workflows/prices.yml` ("Update prices") runs the tests, downloads prices on weekdays at about 6:20pm Melbourne time, commits them and publishes the site.
- Tests: `python3 -m unittest discover -s tests`. Pages source must be set to GitHub Actions.
