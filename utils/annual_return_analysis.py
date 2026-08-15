from __future__ import annotations

import math
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import exchange_calendars as xcals
import pandas as pd


SOURCE_PREFIXES = {
    "ALL": "SXAFI_SX9Q9",
    "SXAFI": "SXAFI",
    "SX9Q9": "SX9Q9",
}

INDEX_TICKERS = {
    "MSCI World": "URTH",
    "S&P 500": "^GSPC",
    "Dow Jones": "^DJI",
    "Nasdaq 100": "^NDX",
    "Russell 2000": "^RUT",
    "Euro Stoxx 50": "^STOXX50E",
    "DAX (Germany)": "^GDAXI",
    "FTSE 100 (UK)": "^FTSE",
    "Nikkei 225 (Japan)": "^N225",
    "Hang Seng Index (Hong Kong)": "^HSI",
    "SSE Composite (Shanghai)": "000001.SS",
    "Nifty 50 (India)": "^NSEI",
    "Bovespa (Brazil)": "^BVSP",
}

DEFAULT_INDEX_NAMES = (
    "MSCI World",
    "S&P 500",
    "Nasdaq 100",
    "FTSE 100 (UK)",
)

TREASURY_10Y_NAME = "US 10Y Treasury Yield"
TREASURY_10Y_TICKER = "^TNX"
TRADING_DAYS_PER_YEAR = 252.0

REQUIRED_PNL_KEYS = {
    "date",
    "market_details",
    "total_daily_pnl",
    "total_fx_pnl",
    "total_market_value",
    "total_non_fx_pnl",
}


@dataclass(frozen=True)
class DailyPnlAudit:
    file_paths: dict[pd.Timestamp, Path]
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    year_summary: pd.DataFrame
    missing_dates: pd.DataFrame
    full_calendar_years: tuple[int, ...]
    complete_trading_years: tuple[int, ...]
    complete_union_years: tuple[int, ...]
    weekend_dates_without_files: int
    weekend_files: tuple[str, ...]
    both_markets_closed_files: tuple[str, ...]


@dataclass(frozen=True)
class AnnualReturnAnalysis:
    metrics: pd.DataFrame
    cumulative_paths: pd.DataFrame
    warnings: tuple[str, ...]


def _normalize_timestamp(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize()


def _calendar_sessions(
    calendar: object,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> set[pd.Timestamp]:
    sessions = calendar.sessions_in_range(start_date, end_date)
    if sessions.tz is not None:
        sessions = sessions.tz_localize(None)
    return set(sessions.normalize())


def _holiday_name(calendar: object, calendar_name: str, day: pd.Timestamp) -> str:
    names = calendar.regular_holidays.holidays(
        start=day,
        end=day,
        return_name=True,
    )
    if not names.empty:
        return str(names.iloc[0])

    ad_hoc_dates = {_normalize_timestamp(value) for value in calendar.adhoc_holidays}
    if day in ad_hoc_dates:
        return f"{calendar_name} ad hoc exchange closure"
    return f"{calendar_name} exchange holiday"


def discover_daily_pnl_files(
    pnl_dir: Path,
    data_source: str = "ALL",
) -> dict[pd.Timestamp, Path]:
    """Return dated PnL pickle paths without opening or modifying the files."""
    try:
        source_prefix = SOURCE_PREFIXES[data_source]
    except KeyError as exc:
        raise ValueError(f"Unsupported data source: {data_source}") from exc

    if not pnl_dir.is_dir():
        raise FileNotFoundError(f"Daily PnL directory does not exist: {pnl_dir}")

    pattern = re.compile(
        rf"^daily_pnl_{re.escape(source_prefix)}_(\d{{8}})\.pkl$"
    )
    file_paths: dict[pd.Timestamp, Path] = {}
    for path in pnl_dir.iterdir():
        match = pattern.match(path.name)
        if not match or not path.is_file():
            continue
        file_date = pd.Timestamp(match.group(1)).normalize()
        if file_date in file_paths:
            raise ValueError(f"Duplicate Daily PnL date found: {file_date.date()}")
        file_paths[file_date] = path

    if not file_paths:
        raise FileNotFoundError(
            f"No Daily PnL files found for data source {data_source}: {pnl_dir}"
        )
    return dict(sorted(file_paths.items()))


def audit_daily_pnl_dates(
    pnl_dir: Path,
    data_source: str = "ALL",
) -> DailyPnlAudit:
    """Audit filenames against NYSE and LSE calendars without opening the data."""
    file_paths = discover_daily_pnl_files(pnl_dir, data_source)
    actual_dates = set(file_paths)
    start_date = min(actual_dates)
    end_date = max(actual_dates)

    nyse = xcals.get_calendar("XNYS")
    lse = xcals.get_calendar("XLON")
    nyse_sessions = _calendar_sessions(nyse, start_date, end_date)
    lse_sessions = _calendar_sessions(lse, start_date, end_date)

    calendar_days = set(pd.date_range(start_date, end_date, freq="D"))
    weekday_dates = {day for day in calendar_days if day.weekday() < 5}
    weekend_dates = calendar_days - weekday_dates
    weekend_files = tuple(
        str(day.date()) for day in sorted(actual_dates & weekend_dates)
    )
    both_markets_closed_dates = weekday_dates - (nyse_sessions | lse_sessions)
    both_markets_closed_files = tuple(
        str(day.date())
        for day in sorted(actual_dates & both_markets_closed_dates)
    )

    missing_records: list[dict[str, object]] = []
    for day in sorted(weekday_dates - actual_dates):
        nyse_open = day in nyse_sessions
        lse_open = day in lse_sessions
        if nyse_open and lse_open:
            classification = "missing_both_markets_open"
            is_true_missing = True
        elif nyse_open:
            classification = "missing_nyse_open_lse_holiday"
            is_true_missing = True
        elif lse_open:
            classification = "nyse_holiday_lse_open"
            is_true_missing = False
        else:
            classification = "both_markets_closed"
            is_true_missing = False

        holiday_parts = []
        if not nyse_open:
            holiday_parts.append(f"NYSE: {_holiday_name(nyse, 'NYSE', day)}")
        if not lse_open:
            holiday_parts.append(f"LSE: {_holiday_name(lse, 'LSE', day)}")
        missing_records.append(
            {
                "date": day,
                "weekday": day.day_name(),
                "classification": classification,
                "nyse_status": "Open" if nyse_open else "Closed",
                "lse_status": "Open" if lse_open else "Closed",
                "holiday_detail": "; ".join(holiday_parts),
                "is_true_missing": is_true_missing,
                "is_union_missing": nyse_open or lse_open,
            }
        )

    missing_dates = pd.DataFrame(missing_records)
    year_records: list[dict[str, object]] = []
    for year in range(start_date.year, end_date.year + 1):
        year_start = pd.Timestamp(year=year, month=1, day=1)
        year_end = pd.Timestamp(year=year, month=12, day=31)
        expected_nyse = _calendar_sessions(nyse, year_start, year_end)
        expected_lse = _calendar_sessions(lse, year_start, year_end)
        expected_union = expected_nyse | expected_lse
        present = {day for day in actual_dates if day.year == year}
        covered_start = max(start_date, min(expected_union))
        covered_end = min(end_date, max(expected_union))
        covered_nyse = {
            day for day in expected_nyse if covered_start <= day <= covered_end
        }
        covered_lse = {
            day for day in expected_lse if covered_start <= day <= covered_end
        }
        missing_nyse = sorted(covered_nyse - present)
        missing_union = sorted((covered_nyse | covered_lse) - present)
        full_calendar_range = (
            start_date <= min(expected_union) and end_date >= max(expected_union)
        )
        trading_data_complete = full_calendar_range and not missing_nyse
        union_data_complete = full_calendar_range and not missing_union

        if trading_data_complete:
            status = "Complete"
        elif full_calendar_range:
            status = "Incomplete trading dates"
        else:
            status = "Partial calendar year"

        uk_only_missing = {
            day
            for day in (expected_lse - expected_nyse) - present
            if covered_start <= day <= covered_end
        }
        year_records.append(
            {
                "year": year,
                "coverage_start": min(present).date() if present else None,
                "coverage_end": max(present).date() if present else None,
                "file_count": len(present),
                "expected_nyse_sessions": len(covered_nyse),
                "missing_nyse_sessions": len(missing_nyse),
                "missing_nyse_dates": ", ".join(
                    str(day.date()) for day in missing_nyse
                ),
                "missing_union_sessions": len(missing_union),
                "missing_union_dates": ", ".join(
                    str(day.date()) for day in missing_union
                ),
                "us_holiday_uk_open_without_file": len(uk_only_missing),
                "extra_non_nyse_files": len(present - expected_nyse),
                "full_calendar_range": full_calendar_range,
                "trading_data_complete": trading_data_complete,
                "union_data_complete": union_data_complete,
                "status": status,
            }
        )

    year_summary = pd.DataFrame(year_records)
    full_calendar_years = tuple(
        int(year)
        for year in year_summary.loc[year_summary["full_calendar_range"], "year"]
    )
    complete_trading_years = tuple(
        int(year)
        for year in year_summary.loc[
            year_summary["trading_data_complete"], "year"
        ]
    )
    complete_union_years = tuple(
        int(year)
        for year in year_summary.loc[year_summary["union_data_complete"], "year"]
    )
    return DailyPnlAudit(
        file_paths=file_paths,
        start_date=start_date,
        end_date=end_date,
        year_summary=year_summary,
        missing_dates=missing_dates,
        full_calendar_years=full_calendar_years,
        complete_trading_years=complete_trading_years,
        complete_union_years=complete_union_years,
        weekend_dates_without_files=len(weekend_dates - actual_dates),
        weekend_files=weekend_files,
        both_markets_closed_files=both_markets_closed_files,
    )


def _as_finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def load_portfolio_daily_returns(
    file_paths: dict[pd.Timestamp, Path],
    years: Iterable[int],
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Read selected pickle files and normalize portfolio daily return fields."""
    selected_years = {int(year) for year in years}
    records: list[dict[str, object]] = []
    warnings: list[str] = []

    for file_date, path in file_paths.items():
        if file_date.year not in selected_years:
            continue
        try:
            with path.open("rb") as handle:
                payload = pickle.load(handle)
        except (OSError, pickle.UnpicklingError, EOFError) as exc:
            warnings.append(f"Could not read {path.name}: {exc}")
            continue
        if not isinstance(payload, dict):
            warnings.append(f"Skipped {path.name}: payload is not a dictionary")
            continue

        missing_keys = REQUIRED_PNL_KEYS - payload.keys()
        if missing_keys:
            warnings.append(
                f"Skipped {path.name}: missing keys {sorted(missing_keys)}"
            )
            continue
        payload_date = _normalize_timestamp(payload["date"])
        if payload_date != file_date:
            warnings.append(
                f"Skipped {path.name}: payload date is {payload_date.date()}"
            )
            continue

        market_value = _as_finite_float(payload["total_market_value"])
        daily_pnl = _as_finite_float(payload["total_daily_pnl"])
        fx_pnl = _as_finite_float(payload["total_fx_pnl"])
        non_fx_pnl = _as_finite_float(payload["total_non_fx_pnl"])
        if market_value in (None, 0.0) or None in (daily_pnl, fx_pnl, non_fx_pnl):
            warnings.append(f"Skipped {path.name}: invalid PnL or market value")
            continue

        records.append(
            {
                "date": file_date,
                "year": file_date.year,
                "daily_return": daily_pnl / market_value,
                "fx_return": fx_pnl / market_value,
                "non_fx_return": non_fx_pnl / market_value,
                "total_daily_pnl": daily_pnl,
                "total_fx_pnl": fx_pnl,
                "total_non_fx_pnl": non_fx_pnl,
                "total_market_value": market_value,
            }
        )

    frame = pd.DataFrame(records)
    if not frame.empty:
        frame = frame.sort_values("date").reset_index(drop=True)
    return frame, tuple(warnings)


def _maximum_drawdown(cumulative_return: pd.Series) -> float:
    if cumulative_return.empty:
        return float("nan")
    running_peak = cumulative_return.cummax()
    return float((cumulative_return / running_peak - 1.0).min())


def _annualized_sharpe_ratio(
    daily_returns: pd.Series,
    annual_risk_free_rate: float | None,
) -> float:
    """Calculate annualized Sharpe from daily returns and an annual risk-free rate."""
    returns = pd.to_numeric(daily_returns, errors="coerce").dropna().astype(float)
    risk_free_rate = _as_finite_float(annual_risk_free_rate)
    if len(returns) < 2 or risk_free_rate is None or risk_free_rate <= -1.0:
        return float("nan")

    daily_volatility = float(returns.std(ddof=1))
    if not math.isfinite(daily_volatility) or daily_volatility == 0.0:
        return float("nan")

    daily_risk_free_rate = math.expm1(
        math.log1p(risk_free_rate) / TRADING_DAYS_PER_YEAR
    )
    return float(
        (returns.mean() - daily_risk_free_rate)
        / daily_volatility
        * math.sqrt(TRADING_DAYS_PER_YEAR)
    )


def build_annual_risk_free_rates(
    treasury_yield_pct: pd.Series,
    period_bounds: dict[int, tuple[pd.Timestamp, pd.Timestamp]],
) -> dict[int, float]:
    """Average daily US 10Y yields for each analysis period as decimal rates."""
    yields = pd.to_numeric(treasury_yield_pct, errors="coerce").dropna().astype(float)
    if yields.empty:
        return {}

    yields.index = pd.to_datetime(yields.index)
    if yields.index.tz is not None:
        yields.index = yields.index.tz_localize(None)
    yields = yields[~yields.index.duplicated(keep="last")].sort_index()

    annual_rates: dict[int, float] = {}
    for year, (period_start, period_end) in sorted(period_bounds.items()):
        period_yields = yields.loc[
            (yields.index >= period_start) & (yields.index <= period_end)
        ]
        if period_yields.empty:
            continue
        annual_rates[int(year)] = float(period_yields.mean()) / 100.0
    return annual_rates


def _comparison_date(value: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(year=2000, month=value.month, day=value.day)


def build_portfolio_annual_analysis(
    daily_returns: pd.DataFrame,
    year_status: dict[int, str],
    risk_free_rates: dict[int, float] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics: list[dict[str, object]] = []
    paths: list[pd.DataFrame] = []
    if daily_returns.empty:
        return pd.DataFrame(), pd.DataFrame()

    for year, year_data in daily_returns.groupby("year", sort=True):
        year_data = year_data.sort_values("date").copy()
        returns = year_data.set_index("date")["daily_return"].astype(float)
        annual_risk_free_rate = (risk_free_rates or {}).get(int(year))
        path_returns = returns.copy()
        path_returns.iloc[0] = 0.0
        cumulative = (1.0 + path_returns).cumprod()
        annualized_volatility = returns.std(ddof=1) * math.sqrt(252.0)
        metrics.append(
            {
                "year": int(year),
                "asset": "Portfolio",
                "annual_return_pct": (float(cumulative.iloc[-1]) - 1.0) * 100.0,
                "annualized_volatility_pct": float(annualized_volatility) * 100.0,
                "max_drawdown_pct": _maximum_drawdown(cumulative) * 100.0,
                "risk_free_rate_pct": (
                    annual_risk_free_rate * 100.0
                    if annual_risk_free_rate is not None
                    else float("nan")
                ),
                "sharpe_ratio": _annualized_sharpe_ratio(
                    returns,
                    annual_risk_free_rate,
                ),
                "observations": len(year_data),
                "period_start": year_data["date"].iloc[0],
                "period_end": year_data["date"].iloc[-1],
                "total_pnl_gbp": year_data["total_daily_pnl"].sum(),
                "total_fx_pnl_gbp": year_data["total_fx_pnl"].sum(),
                "status": year_status.get(int(year), "Unknown"),
            }
        )
        path = pd.DataFrame(
            {
                "date": cumulative.index,
                "year": int(year),
                "asset": "Portfolio",
                "cumulative_return": cumulative.to_numpy(),
            }
        )
        path["comparison_date"] = path["date"].map(_comparison_date)
        paths.append(path)

    return pd.DataFrame(metrics), pd.concat(paths, ignore_index=True)


def _extract_close_series(downloaded: pd.DataFrame, ticker: str) -> pd.Series:
    if downloaded.empty:
        return pd.Series(dtype=float)
    if isinstance(downloaded.columns, pd.MultiIndex):
        level_zero = downloaded.columns.get_level_values(0)
        level_one = downloaded.columns.get_level_values(1)
        if ticker in level_zero:
            ticker_frame = downloaded[ticker]
            if "Close" in ticker_frame.columns:
                return ticker_frame["Close"]
        if "Close" in level_zero and ticker in level_one:
            return downloaded["Close"][ticker]
        return pd.Series(dtype=float)
    if "Close" in downloaded.columns:
        return downloaded["Close"]
    return pd.Series(dtype=float)


def _fetch_named_close_prices(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    name_to_ticker: dict[str, str],
    data_label: str,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Fetch named close series in one yfinance request."""
    import yfinance as yf

    if not name_to_ticker:
        return pd.DataFrame(), ()
    tickers = list(name_to_ticker.values())
    try:
        downloaded = yf.download(
            tickers=tickers,
            start=start_date.strftime("%Y-%m-%d"),
            end=(end_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
            timeout=30,
        )
    except Exception as exc:
        return pd.DataFrame(), (f"{data_label} download failed: {exc}",)

    close_prices: dict[str, pd.Series] = {}
    warnings: list[str] = []
    for name, ticker in name_to_ticker.items():
        close = pd.to_numeric(
            _extract_close_series(downloaded, ticker),
            errors="coerce",
        ).dropna()
        if close.empty:
            warnings.append(f"No {data_label.lower()} data returned for {name} ({ticker})")
            continue
        close.index = pd.to_datetime(close.index)
        if close.index.tz is not None:
            close.index = close.index.tz_localize(None)
        close_prices[name] = close[~close.index.duplicated(keep="last")]

    if not close_prices:
        return pd.DataFrame(), tuple(warnings)
    return pd.DataFrame(close_prices).sort_index(), tuple(warnings)


def fetch_index_close_prices(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    index_names: Iterable[str],
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Fetch selected benchmark closes in one yfinance request."""
    selected_tickers = {
        name: INDEX_TICKERS[name]
        for name in index_names
        if name in INDEX_TICKERS
    }
    return _fetch_named_close_prices(
        start_date,
        end_date,
        selected_tickers,
        data_label="Index",
    )


def fetch_annual_market_close_prices(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    index_names: Iterable[str],
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Fetch selected benchmarks and the US 10Y Treasury yield together."""
    selected_tickers = {
        name: INDEX_TICKERS[name]
        for name in index_names
        if name in INDEX_TICKERS
    }
    selected_tickers[TREASURY_10Y_NAME] = TREASURY_10Y_TICKER
    return _fetch_named_close_prices(
        start_date,
        end_date,
        selected_tickers,
        data_label="Market",
    )


def build_index_annual_analysis(
    close_prices: pd.DataFrame,
    period_bounds: dict[int, tuple[pd.Timestamp, pd.Timestamp]],
    year_status: dict[int, str],
    risk_free_rates: dict[int, float] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics: list[dict[str, object]] = []
    paths: list[pd.DataFrame] = []
    if close_prices.empty:
        return pd.DataFrame(), pd.DataFrame()

    for year, (period_start, period_end) in sorted(period_bounds.items()):
        annual_risk_free_rate = (risk_free_rates or {}).get(int(year))
        period_prices = close_prices.loc[
            (close_prices.index >= period_start) & (close_prices.index <= period_end)
        ]
        for asset in close_prices.columns:
            prices = period_prices[asset].dropna().astype(float)
            if prices.empty:
                continue
            cumulative = prices / prices.iloc[0]
            returns = prices.pct_change().dropna()
            annualized_volatility = returns.std(ddof=1) * math.sqrt(252.0)
            metrics.append(
                {
                    "year": int(year),
                    "asset": str(asset),
                    "annual_return_pct": (float(cumulative.iloc[-1]) - 1.0) * 100.0,
                    "annualized_volatility_pct": float(annualized_volatility) * 100.0,
                    "max_drawdown_pct": _maximum_drawdown(cumulative) * 100.0,
                    "risk_free_rate_pct": (
                        annual_risk_free_rate * 100.0
                        if annual_risk_free_rate is not None
                        else float("nan")
                    ),
                    "sharpe_ratio": _annualized_sharpe_ratio(
                        returns,
                        annual_risk_free_rate,
                    ),
                    "observations": len(prices),
                    "period_start": prices.index[0],
                    "period_end": prices.index[-1],
                    "total_pnl_gbp": float("nan"),
                    "total_fx_pnl_gbp": float("nan"),
                    "status": year_status.get(int(year), "Unknown"),
                }
            )
            path = pd.DataFrame(
                {
                    "date": cumulative.index,
                    "year": int(year),
                    "asset": str(asset),
                    "cumulative_return": cumulative.to_numpy(),
                }
            )
            path["comparison_date"] = path["date"].map(_comparison_date)
            paths.append(path)

    metrics_frame = pd.DataFrame(metrics)
    paths_frame = pd.concat(paths, ignore_index=True) if paths else pd.DataFrame()
    return metrics_frame, paths_frame


def run_annual_return_analysis(
    audit: DailyPnlAudit,
    years: Iterable[int],
    index_names: Iterable[str],
) -> AnnualReturnAnalysis:
    """Build annual portfolio and benchmark comparisons without writing data."""
    selected_years = tuple(sorted({int(year) for year in years}))
    if not selected_years:
        raise ValueError("At least one analysis year is required")

    daily_returns, load_warnings = load_portfolio_daily_returns(
        audit.file_paths,
        selected_years,
    )
    if daily_returns.empty:
        raise ValueError("No valid Daily PnL observations found for selected years")

    year_status = audit.year_summary.set_index("year")["status"].to_dict()
    period_bounds = {
        int(year): (group["date"].min(), group["date"].max())
        for year, group in daily_returns.groupby("year")
    }
    index_start = min(start for start, _ in period_bounds.values())
    index_end = max(end for _, end in period_bounds.values())
    market_close_prices, market_warnings = fetch_annual_market_close_prices(
        index_start,
        index_end,
        index_names,
    )
    treasury_yield_pct = pd.Series(dtype=float)
    if TREASURY_10Y_NAME in market_close_prices.columns:
        treasury_yield_pct = market_close_prices.pop(TREASURY_10Y_NAME)
    risk_free_rates = build_annual_risk_free_rates(
        treasury_yield_pct,
        period_bounds,
    )
    risk_free_warnings = tuple(
        f"No US 10Y Treasury yield data for {year}; Sharpe ratio is unavailable."
        for year in period_bounds
        if year not in risk_free_rates
    )

    portfolio_metrics, portfolio_paths = build_portfolio_annual_analysis(
        daily_returns,
        year_status,
        risk_free_rates=risk_free_rates,
    )
    index_metrics, index_paths = build_index_annual_analysis(
        market_close_prices,
        period_bounds,
        year_status,
        risk_free_rates=risk_free_rates,
    )

    metrics = pd.concat(
        [frame for frame in (portfolio_metrics, index_metrics) if not frame.empty],
        ignore_index=True,
    )
    paths = pd.concat(
        [frame for frame in (portfolio_paths, index_paths) if not frame.empty],
        ignore_index=True,
    )
    return AnnualReturnAnalysis(
        metrics=metrics,
        cumulative_paths=paths,
        warnings=tuple(
            (*load_warnings, *market_warnings, *risk_free_warnings)
        ),
    )
