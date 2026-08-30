# Change Log

This file records substantial project changes. Add new entries under
`Unreleased`; keep small formatting and comment-only edits out of the log.

## Unreleased
### Portfolio Analysis
- 2026-08-17: Extended the global-index cumulative-return table with selected-
  period annualized volatility. Added an interactive percentile heatmap that
  compares Portfolio with the global indices across period cumulative return,
  calendar-YTD maximum drawdown, and annualized volatility. Higher percentiles
  consistently mean better outcomes: higher return, shallower drawdown, and
  lower volatility. Portfolio is highlighted and each cell exposes actual
  value, percentile, and rank. Validation: focused offline tests, syntax and
  whitespace checks, and a live Streamlit workflow smoke test.

- 2026-08-17: Added annualized S&P 500 and NASDAQ volatility beneath FX
  contribution volatility in the cumulative-contribution summary. Both use
  close-to-close daily returns over the selected period and 252-day
  annualization; unavailable or insufficient index data is displayed as `N/A`.
  The summary is grouped into annualized metrics followed by period cumulative
  contribution and PnL metrics. The annualized section now also shows calendar
  YTD maximum drawdown for the Portfolio, S&P 500, and NASDAQ; the global-index
  comparison table includes the same YTD maximum-drawdown column for every
  index.

- 2026-08-16: Optimized the portfolio drawdown monitor by replacing sequential
  per-ticker Yahoo history and info requests with one threaded yfinance batch
  download for all current positions. The same in-memory adjusted-close data
  now supports lookback drawdowns, selected price-distribution charts, and
  as-of-date 52-week ranges. Chart definitions and the selected-lookback price
  standard-deviation marker are unchanged; no investment or PnL data is
  written. Validation: offline drawdown tests and a live before/after timing
  benchmark using representative US and LSE holdings.

- 2026-08-12: Extended historical annual-return analysis with a Portfolio
  annual summary showing total PnL in GBP for each selected year. Comparison
  metrics now include annualized Sharpe ratio. The risk-free rate is the mean
  daily US 10-year Treasury yield (`^TNX`) over each year's actual analysis
  period, and Sharpe is calculated from daily excess returns using 252 trading
  days. Benchmark and Treasury data are downloaded together; missing Treasury
  data produces a warning and leaves Sharpe unavailable without failing the
  remaining analysis. No Daily PnL or investment data is written or modified.
  Validation: 15 offline tests, a live Treasury/index data smoke test, live
  Streamlit interaction verification, and a Daily PnL directory fingerprint
  check.

- 2026-08-11: Replaced the drawdown monitor's all-position 52-week range chart
  with selectable price distribution charts. The Streamlit multiselect is
  sourced from every `current_positions` entry, starts empty, and accepts up to
  10 positions. Each selected ticker is drawn in a separate chart with its own
  dynamic local-price range, distribution color, latest-price marker, and mean
  +/- one sample standard deviation marker; each new run replaces all previous
  drawdown charts. The compact charts use a dark visual theme and are displayed
  in a responsive two-column Streamlit grid. Yahoo `info` does not expose a
  standard-deviation field, so 1 SD is calculated from each security's same
  lookback closing-price series. Single-string IDE calls remain compatible. The
  existing portfolio drawdown table and calculations are unchanged. No
  investment data is written. Validation: 14 offline tests, syntax checks, a
  live yfinance chart smoke test, and live Streamlit UI verification.

- 2026-08-11: Added a read-only historical annual-return analysis section to
  Streamlit. It audits Daily PnL filename coverage against NYSE and LSE
  calendars, separates true missing trading days from weekends and exchange
  holidays, identifies full calendar years, and compares Portfolio returns,
  volatility, drawdown, and cumulative paths with selectable global indices.
  Existing report, save, and follow-up workflows are unchanged, and no Daily
  PnL file is written or modified. Validation: offline unit tests, full local
  pickle smoke test, Streamlit UI verification, and directory fingerprint check.

- 2026-08-10: Added an interactive Strategy cumulative-return chart to the
  cumulative-contribution workflow. The chart excludes Money Market, then
  displays the five strategies with the largest market values on the latest
  available date. It compounds daily Strategy PnL divided by Strategy market
  value from a Base=1 start and uses the existing Strategy fallback rules.
  Missing strategy dates contribute zero. The Strategy legend is clickable:
  the selected path is emphasized while unselected paths fade. Streamlit renders
  both cumulative charts in order with shared hover dates and vertical
  crosshairs. Both charts retain every dated observation and use an adaptive
  date axis: weekly DD-Mon-YY ticks for short ranges and monthly Mon-YY ticks
  for longer ranges, with the exact date remaining available on hover. No persisted data schema
  changes. Validation: aggregation unit tests, syntax checks, local-PnL smoke
  test, Altair chart smoke test, and live Streamlit verification.

- 2026-08-09: Removed current-price and average-buy-price columns from the
  strategy-level holdings tables in both Streamlit and the console report,
  because those local-currency prices are not meaningful across aggregated
  positions. Position-level holdings remain unchanged. Validation: focused
  table checks, syntax checks, live Streamlit verification, and whitespace
  checks.

- 2026-08-08: Added a strategy-level holdings table to the console PnL report
  and Streamlit holdings tabs. Amounts are summed by strategy, percentage
  returns are recalculated from aggregate amounts, and holding days use a
  market-value-weighted average. No persisted data schema changes. Validation:
  aggregation unit tests, Python syntax checks, and whitespace checks.


### Governance

- 2026-08-09: Added explicit approval boundaries for modifying or deleting
  existing files and project-folder hygiene rules that prohibit transient
  artifacts. Reduced mandatory operational-memory loading by selecting lessons
  by trigger instead of reading the growing reference in full. No runtime or
  data-schema impact. Validation: instruction checks, skill validation, and
  whitespace checks.

- 2026-08-08: Added mandatory project operational memory for reusing confirmed
  lessons from earlier failures. Initial lessons cover the canonical Yikai
  virtual-environment interpreter, sandbox escalation behavior, stale Streamlit
  processes, end-to-end consumer validation, and protected `.agents` writes.
  No runtime behavior or data migration impact. Validation: skill schema and
  mandatory-read path checks.

- 2026-08-08: Added mandatory repository coding-practice guidance covering
  architecture, error handling, testing, OOP, reuse, modularity, naming,
  readability, data integrity, and substantial-change logging. No runtime
  behavior or migration impact. Validation: skill schema validation and
  instruction-path checks.
