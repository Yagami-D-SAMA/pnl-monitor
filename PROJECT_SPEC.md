# PROJECT_SPEC.md

## 1. Project goal

Build a local Python research/data workflow for:

1. portfolio positions,
2. market data,
3. dividends,
4. data QA,
5. local storage,
6. repeatable research outputs.

The project should remain local-first and incremental. Existing portfolio-analysis code, ticker mappings, data loaders, reports, and storage patterns should be reused wherever possible.

## 2. Current dividend workflow goal

For all current portfolio positions, retrieve dividend payment dates for:

1. the current month,
2. the next month.

The workflow should focus on current holdings first. It should not attempt to build a full dividend forecasting platform until the first local workflow is reliable.

## 3. Target dividend output schema

The target output should include these columns:

```text
ticker
position_name if available
quantity if available
ex_dividend_date
record_date if available
payment_date
dividend_amount
currency if available
estimated_cash_dividend
data_source
```

`estimated_cash_dividend` should be calculated as:

```text
quantity * dividend_amount
```

when both fields are available. If either field is missing, the value should be left empty or marked unavailable rather than guessed.

## 4. Data source preference

Provider priority:

1. Reuse existing project data providers if present.
2. Otherwise use `yfinance` as the first simple provider.
3. Design a provider interface so FMP, Finnhub, or another dividend provider can be added later.

The first implementation should avoid locking the project into one external API shape. Provider-specific fields should be normalized into the target output schema.

## 5. Storage

- Save processed dividend outputs as Parquet.
- Optionally also save CSV for manual review.
- Keep outputs local.
- Do not commit downloaded or generated data outputs.
- Prefer paths that make the date window and data purpose clear.

Example storage intent:

```text
data/processed/dividends/
data/processed/dividends_review/
```

Actual paths should follow existing project conventions if they already exist.

## 6. Testing requirements

Add tests for reusable dividend workflow logic:

1. date filtering for current month and next month,
2. estimated dividend calculation,
3. empty or no-dividend response,
4. API failure should warn but not crash.

Tests should not depend on live API calls by default. Use fixtures or fake provider responses for unit tests.

## 7. Command-line entry

Prefer the existing project convention for command-line or script entry.

If no clear convention exists, propose a simple command before implementing, such as:

```bash
python -m portfolio_analysis dividends --date YYYY-MM-DD --data-source ALL
```

or a project-consistent function entry from `portfolio_analysis.py`.

Do not add a new CLI framework unless explicitly requested.

## 8. Near-term implementation boundary

The dividend workflow should be implemented in small steps:

1. inspect existing portfolio position loading,
2. define a small provider interface,
3. add a simple `yfinance` provider if no existing provider fits,
4. normalize provider data into the target schema,
5. filter to current month and next month,
6. calculate estimated cash dividend,
7. save processed Parquet and optional CSV,
8. add tests.

Do not implement broader portfolio construction, scheduling, database storage, or a full dividend forecasting engine unless explicitly requested.

