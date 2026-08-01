import pandas as pd
from datetime import datetime, timedelta
import os
import pickle
from tabulate import tabulate
import yfinance as yf
import matplotlib.pyplot as plt
from utils.Calculator import is_weekend
from pathlib import Path
import re
from utils.ticker_harvest import read_h5, OUTPUT_DIR, H5_KEY
from utils.FundamentalData import fetch_earnings_batch
from datetime import date, datetime, timedelta

BANK_HOLIDAYS: set[date] = {
    date(2026, 5, 25),
    # date(2025, 12, 25),  # 示例：按需添加
}
def is_bank_holiday(d: date) -> bool:
    return d in BANK_HOLIDAYS
def is_business_day(d: date) -> bool:
    return not is_weekend(d) and not is_bank_holiday(d)

# def get_previous_business_day(target_date: datetime) -> datetime:
#     # 先从前一天开始
#     prev_date = target_date - timedelta(days=1)
#
#     # 如果是周末，就一直往前减一天，直到不是周末
#     while is_weekend(prev_date.date()):
#         prev_date -= timedelta(days=1)
#
#     return prev_date

def get_previous_business_day(target_date: datetime) -> datetime:
    prev_date = target_date - timedelta(days=1)
    while not is_business_day(prev_date.date()):
        prev_date -= timedelta(days=1)
    return prev_date

def _load_local_env_if_needed() -> None:
    """Load root .env values into os.environ without overriding existing environment variables."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

def _read_slickcharts_weight_table(url: str) -> pd.DataFrame:
    from io import BytesIO
    from urllib.request import Request, urlopen

    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=30) as response:
        html = response.read()

    tables = pd.read_html(BytesIO(html))
    for table in tables:
        table.columns = [str(col).strip() for col in table.columns]
        if {"Company", "Symbol", "Weight"}.issubset(table.columns):
            return table

    raise ValueError(f"No constituent weight table found from {url}")

def display_index_top_constituents_performance(top_n: int = 10) -> None:
    """Display today's top-weighted S&P 500 and Nasdaq 100 constituent performance."""
    index_sources = {
        "S&P 500": "https://www.slickcharts.com/sp500",
        "NASDAQ 100": "https://www.slickcharts.com/nasdaq100",
    }

    for index_name, url in index_sources.items():
        try:
            constituents = _read_slickcharts_weight_table(url).head(top_n).copy()
            display_columns = [
                col for col in ["Company", "Symbol", "Weight", "Price", "Chg", "% Chg"]
                if col in constituents.columns
            ]
            print(f"\n{index_name} 当天weight排名Top {top_n} constituents daily performance:")
            print("-" * 100)
            print(tabulate(
                constituents[display_columns],
                headers="keys",
                tablefmt="fancy_grid",
                showindex=False,
                disable_numparse=True,
            ))
        except Exception as e:
            print(f"{index_name} Top {top_n} constituents performance 获取失败: {e}")

def _resolve_target_date(target_date: object = None) -> datetime:
    if target_date is None:
        target_date = datetime.today()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d')
    return target_date.replace(hour=23, minute=30, second=0, microsecond=0)

def _resolve_trade_history_paths(investment_dir: str, data_source: object):
    trade_history_path_SXAFI = os.path.join(investment_dir, 'TradeHistory-SXAFI.csv')
    trade_history_path_SX9Q9 = os.path.join(investment_dir, 'TradeHistory-SX9Q9.csv')

    trade_history_paths = []
    if data_source == 'SXAFI':
        trade_history_paths.append(trade_history_path_SXAFI)
    elif data_source == 'SX9Q9':
        trade_history_paths.append(trade_history_path_SX9Q9)
    elif data_source == 'ALL':
        trade_history_paths.extend([trade_history_path_SXAFI, trade_history_path_SX9Q9])
    else:
        print(f"错误：无效的数据源选择 {data_source}，请使用 'SXAFI'、'SX9Q9' 或 'ALL'")
        return None

    return trade_history_paths

def _load_portfolio_context(target_date: object = None, data_source: object = None):
    target_date = _resolve_target_date(target_date)
    prev_date = get_previous_business_day(target_date)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    investment_dir = os.path.join(base_dir, 'investment')
    dvd_history_path = os.path.join(investment_dir, 'DvdHistory.csv')
    enum_path = os.path.join(investment_dir, 'enum.csv')
    trade_history_paths = _resolve_trade_history_paths(investment_dir, data_source)
    if trade_history_paths is None:
        return None

    for path in trade_history_paths:
        if not os.path.exists(path):
            print(f"错误：无法找到交易历史文件 - {path}")
            return None
    if not os.path.exists(enum_path):
        print(f"错误：无法找到枚举文件 - {enum_path}")
        return None
    if not os.path.exists(dvd_history_path):
        print(f"错误：无法找到股息历史文件 - {dvd_history_path}")
        return None

    from . import DataLoader
    from . import Calculator

    data_loader = DataLoader(investment_dir, trade_history_paths, enum_path, dvd_history_path, target_date)
    trades_df, enum_df, dvd_df = data_loader.load_trade_data()
    if trades_df is None or enum_df is None or dvd_df is None:
        return None

    market_ticker_map = data_loader.get_market_ticker_map()
    calculator = Calculator()
    current_positions, closed_positions = calculator.calculate_positions(trades_df, dvd_df)

    return {
        "target_date": target_date,
        "prev_date": prev_date,
        "investment_dir": investment_dir,
        "trade_history_paths": trade_history_paths,
        "data_loader": data_loader,
        "trades_df": trades_df,
        "enum_df": enum_df,
        "dvd_df": dvd_df,
        "market_ticker_map": market_ticker_map,
        "calculator": calculator,
        "current_positions": current_positions,
        "closed_positions": closed_positions,
    }

def analyze_portfolio(
    target_date: object = None,
    data_source: object = None,
    asset_type: bool = True,
    overwrite_existing=None,
    prompt_for_constituents: bool = True,
    save_results: bool = True,
) -> object:
    """主函数：分析投资组合"""
    try:
        # 加载数据
        from . import generate_report
        portfolio_context = _load_portfolio_context(target_date, data_source)
        if portfolio_context is None:
            return

        target_date = portfolio_context["target_date"]
        prev_date = portfolio_context["prev_date"]
        trade_history_paths = portfolio_context["trade_history_paths"]
        data_loader = portfolio_context["data_loader"]
        trades_df = portfolio_context["trades_df"]
        market_ticker_map = portfolio_context["market_ticker_map"]
        calculator = portfolio_context["calculator"]
        current_positions = portfolio_context["current_positions"]
        closed_positions = portfolio_context["closed_positions"]

        # 获取汇率数据
        GBPUSD_FX, GBPUSD_FX_prev = data_loader.get_fx_rates(target_date)
        market_comp_rtn = data_loader.get_market_comp_rtn(target_date,['^GSPC', 'ES=F', '^NDX'], prev_date)
        # 计算市场价值和盈亏
        daily_pnl_data, total_market_value, total_pnl, total_cost, region_pnl, region_market_value, strategy_pnl, strategy_market_value, total_market_value_usd, \
            total_market_value_gbp = calculator.calculate_market_values(current_positions, market_ticker_map,
                                                                        target_date, prev_date, GBPUSD_FX, GBPUSD_FX_prev, market_comp_rtn)
        # 计算已实现盈亏
        realized_pnl = calculator.calculate_realized_pnl(trades_df, trades_df['Market'].unique(), closed_positions)
        asset_type_pct = None
        if asset_type:
            asset_type_pct = calculator.asset_type_calc(daily_pnl_data)
            table_data = [
                [entry['asset_type'], f"{entry['percentage'] * 100:.2f}%"]
                for entry in asset_type_pct
            ]
            print(tabulate(table_data, headers=["Asset Type", "Market Value %"], tablefmt="fancy_grid"))
        
        # 显示货币市值分布和汇率信息
        print("\n货币市值分布:")
        
        # 计算百分比
        usd_gbp_value = total_market_value_usd / GBPUSD_FX
        usd_percentage = (usd_gbp_value / total_market_value) * 100 if total_market_value > 0 else 0
        gbp_percentage = (total_market_value_gbp / total_market_value) * 100 if total_market_value > 0 else 0
        gbp_usd_bps = (GBPUSD_FX - GBPUSD_FX_prev) * 10000
        
        currency_data = [
            ["USD市值", f"{total_market_value_usd:,.2f}", "USD"],
            ["USD资产(GBP)", f"{usd_gbp_value:,.2f}", "GBP"],
            ["USD资产%", f"{usd_percentage:.2f}%", ""],
            ["GBP市值", f"{total_market_value_gbp:,.2f}", "GBP"],
            ["GBP资产%", f"{gbp_percentage:.2f}%", ""],
            ["总市值", f"{total_market_value:,.2f}", "GBP"],
            ["当日GBP/USD", f"{GBPUSD_FX:.4f}", ""],
            ["当日GBP/USD move", f"{gbp_usd_bps:.4f}", "bps"]
        ]
        print(tabulate(currency_data, headers=["项目", "数值", "单位"], disable_numparse=[0, 1, 2]))
        
        # 生成报告
        daily_pnl_result = generate_report(
            daily_pnl_data, total_market_value, total_pnl, total_cost, realized_pnl, target_date, region_pnl, region_market_value, strategy_pnl, strategy_market_value)
        # 保存结果
        if save_results:
            data_loader.save_results(daily_pnl_result, trade_history_paths, overwrite_existing=overwrite_existing)
        if prompt_for_constituents:
            try:
                run_constituents = input(
                    "是否显示S&P500和NASDAQ当天weight排名Top 10 constituents的daily performance? (y/N): "
                ).strip().lower()
            except EOFError:
                run_constituents = "n"

            if run_constituents in {"y", "yes", "是"}:
                display_index_top_constituents_performance(top_n=10)

        return {
            "daily_pnl_result": daily_pnl_result,
            "data_loader": data_loader,
            "trade_history_paths": trade_history_paths,
            "target_date": target_date,
            "trades_df": trades_df,
            "current_positions": current_positions,
            "market_ticker_map": market_ticker_map,
            "asset_type_pct": asset_type_pct,
            "currency_summary": {
                "total_market_value_usd": total_market_value_usd,
                "usd_gbp_value": usd_gbp_value,
                "usd_percentage": usd_percentage / 100,
                "total_market_value_gbp": total_market_value_gbp,
                "gbp_percentage": gbp_percentage / 100,
                "total_market_value": total_market_value,
                "gbpusd_fx": GBPUSD_FX,
                "gbpusd_move_bps": gbp_usd_bps,
            },
            "portfolio_summary": {
                "total_market_value": total_market_value,
                "total_cost": total_cost,
                "total_pnl": total_pnl,
                "realized_pnl": realized_pnl,
                "total_pnl_including_realized": total_pnl + realized_pnl,
            },
            "region_pnl": region_pnl,
            "strategy_pnl": strategy_pnl,
            "region_market_value": region_market_value,
            "strategy_market_value": strategy_market_value,
        }

    except Exception as e:
        print(f"分析过程中发生错误: {e}")

def portfolio_drawdown_monitor(running_date: object = None, lookback_period: int = 90, data_source: object = 'ALL') -> pd.DataFrame:
    """Monitor max drawdown for current portfolio positions over a lookback period."""
    portfolio_context = _load_portfolio_context(running_date, data_source)
    if portfolio_context is None:
        return pd.DataFrame()

    running_date = portfolio_context["target_date"]
    current_positions = portfolio_context["current_positions"]
    market_ticker_map = portfolio_context["market_ticker_map"]
    start_date = running_date - pd.Timedelta(days=lookback_period)
    end_date = running_date + pd.Timedelta(days=1)

    drawdown_rows = []
    for market, position_data in current_positions.items():
        ticker = market_ticker_map.get(market)
        if not ticker:
            print(f"{market}: enum.csv 中没有ticker mapping，跳过")
            continue

        try:
            stock = yf.Ticker(ticker)
            hist_data = stock.history(start=start_date, end=end_date)
            if hist_data.empty or "Close" not in hist_data.columns:
                print(f"{ticker}: 没有可用价格数据，跳过")
                continue

            close_prices = hist_data["Close"].dropna()
            if close_prices.empty:
                print(f"{ticker}: Close价格为空，跳过")
                continue

            running_peak = close_prices.cummax()
            drawdown = close_prices / running_peak - 1
            max_drawdown = drawdown.min()
            trough_date = drawdown.idxmin()
            peak_date = close_prices.loc[:trough_date].idxmax()
            current_drawdown = close_prices.iloc[-1] / running_peak.iloc[-1] - 1
            info = stock.info or {}
            fifty_two_week_low = info.get("fiftyTwoWeekLow")
            fifty_two_week_high = info.get("fiftyTwoWeekHigh")
            if fifty_two_week_low is None or fifty_two_week_high is None:
                print(f"{ticker}: yf.info 中没有 fiftyTwoWeekLow/fiftyTwoWeekHigh")
            if (
                fifty_two_week_low is not None
                and fifty_two_week_high is not None
                and fifty_two_week_high > fifty_two_week_low
            ):
                fifty_two_week_position_pct = (
                    (close_prices.iloc[-1] - fifty_two_week_low)
                    / (fifty_two_week_high - fifty_two_week_low)
                ) * 100
            else:
                fifty_two_week_position_pct = None

            drawdown_rows.append({
                "market": market,
                "ticker": ticker,
                "position": position_data.get("position"),
                "latest_date": close_prices.index[-1].strftime("%Y-%m-%d"),
                "latest_price": close_prices.iloc[-1],
                "peak_date": peak_date.strftime("%Y-%m-%d"),
                "peak_price": close_prices.loc[peak_date],
                "trough_date": trough_date.strftime("%Y-%m-%d"),
                "trough_price": close_prices.loc[trough_date],
                "max_drawdown": max_drawdown,
                "current_drawdown": current_drawdown,
                "52_week_low": fifty_two_week_low,
                "52_week_high": fifty_two_week_high,
                "52_week_position_pct": fifty_two_week_position_pct,
            })
        except Exception as e:
            print(f"{ticker}: 计算回撤时发生错误: {e}")

    if not drawdown_rows:
        print("没有生成任何回撤结果")
        return pd.DataFrame()

    result_df = pd.DataFrame(drawdown_rows).sort_values("current_drawdown")
    display_df = result_df.copy()
    display_df["latest_price"] = display_df["latest_price"].map(lambda x: f"{x:,.2f}")
    display_df["peak_price"] = display_df["peak_price"].map(lambda x: f"{x:,.2f}")
    display_df["trough_price"] = display_df["trough_price"].map(lambda x: f"{x:,.2f}")
    display_df["max_drawdown"] = display_df["max_drawdown"].map(lambda x: f"{x * 100:.2f}%")
    display_df["current_drawdown"] = display_df["current_drawdown"].map(lambda x: f"{x * 100:.2f}%")
    display_df["52_week_low"] = display_df["52_week_low"].map(lambda x: "" if pd.isna(x) else f"{x:,.2f}")
    display_df["52_week_high"] = display_df["52_week_high"].map(lambda x: "" if pd.isna(x) else f"{x:,.2f}")
    display_df["52_week_position_pct"] = display_df["52_week_position_pct"].map(
        lambda x: "" if pd.isna(x) else f"{x:.1f}%"
    )

    print(f"\nPortfolio Drawdown Monitor ({running_date.strftime('%Y-%m-%d')}, lookback {lookback_period} days)")
    print("-" * 140)
    print(tabulate(
        display_df[
            [
                "ticker",
                "market",
                "position",
                "latest_date",
                "latest_price",
                "peak_date",
                "peak_price",
                "trough_date",
                "trough_price",
                "max_drawdown",
                "current_drawdown",
                "52_week_low",
                "52_week_high",
                "52_week_position_pct",
            ]
        ],
        headers="keys",
        tablefmt="fancy_grid",
        showindex=False,
        disable_numparse=True,
    ))

    plot_df = result_df.dropna(subset=["52_week_low", "52_week_high", "latest_price", "52_week_position_pct"]).copy()
    plot_df = plot_df[plot_df["52_week_high"] > plot_df["52_week_low"]]
    if plot_df.empty:
        print("没有足够的52 week区间数据用于画图")
    else:
        plot_df = plot_df.sort_values("current_drawdown")
        labels = plot_df["ticker"] + " | " + plot_df["market"]
        y_positions = range(len(plot_df))

        plt.figure(figsize=(12, max(6, len(plot_df) * 0.45)))
        plt.hlines(
            y=y_positions,
            xmin=0,
            xmax=100,
            color="#9aa0a6",
            linewidth=5,
            alpha=0.8,
            label="52 Week Range",
        )
        plt.scatter(
            plot_df["52_week_position_pct"],
            y_positions,
            color="#d62728",
            s=80,
            zorder=3,
            label="Current Price",
        )
        for y, (_, row) in zip(y_positions, plot_df.iterrows()):
            plt.text(
                row["52_week_position_pct"],
                y + 0.15,
                f"{row['latest_price']:,.2f}",
                ha="center",
                fontsize=8,
            )
            plt.text(0, y - 0.2, f"L {row['52_week_low']:,.2f}", ha="left", fontsize=8, color="#5f6368")
            plt.text(100, y - 0.2, f"H {row['52_week_high']:,.2f}", ha="right", fontsize=8, color="#5f6368")

        plt.yticks(list(y_positions), labels)
        plt.xlim(-3, 103)
        plt.xlabel("Position in 52 Week Range (Low = 0%, High = 100%)")
        plt.title(f"Current Price Position vs 52 Week Range ({running_date.strftime('%Y-%m-%d')})")
        plt.grid(axis="x", alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.show()

    return result_df

class DividendProvider:
    """Minimal dividend provider interface for upcoming dividend display."""

    data_source = "unknown"

    def fetch_next_dividend(self, ticker: str, as_of_date: datetime | None = None) -> dict | None:
        raise NotImplementedError


def _first_non_empty(value):
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    if isinstance(value, pd.Series):
        non_empty = value.dropna()
        return non_empty.iloc[0] if not non_empty.empty else None
    return value


def _normalize_optional_date(value):
    value = _first_non_empty(value)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return parsed.date()


def _calendar_lookup(calendar, candidates: list[str]):
    if calendar is None:
        return None

    candidate_map = {candidate.lower(): candidate for candidate in candidates}

    if isinstance(calendar, dict):
        for key, value in calendar.items():
            if str(key).strip().lower() in candidate_map:
                return value
        return None

    if isinstance(calendar, pd.DataFrame):
        for index_value in calendar.index:
            if str(index_value).strip().lower() in candidate_map:
                row = calendar.loc[index_value]
                return _first_non_empty(row)
        for column in calendar.columns:
            if str(column).strip().lower() in candidate_map:
                return _first_non_empty(calendar[column])

    if isinstance(calendar, pd.Series):
        for index_value, value in calendar.items():
            if str(index_value).strip().lower() in candidate_map:
                return value

    return None


def _normalize_optional_number(value):
    value = _first_non_empty(value)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return float(parsed)


def _latest_dividend_amount(stock, ex_dividend_date=None):
    try:
        dividends = stock.dividends
    except Exception:
        return None

    if dividends is None or dividends.empty:
        return None

    dividends = dividends.dropna()
    if dividends.empty:
        return None

    if ex_dividend_date is not None:
        dividend_dates = pd.to_datetime(dividends.index).tz_localize(None).date
        matched = dividends[dividend_dates == ex_dividend_date]
        if not matched.empty:
            return float(matched.iloc[-1])

    return float(dividends.iloc[-1])


def _first_present(row: dict, keys: list[str]):
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _current_and_next_month_window(running_date: datetime) -> tuple[pd.Timestamp, pd.Timestamp]:
    month_start = pd.Timestamp(running_date.date()).replace(day=1)
    month_after_next_start = month_start + pd.DateOffset(months=2)
    return month_start, month_after_next_start


class YFinanceDividendProvider(DividendProvider):
    """Simple yfinance-backed provider for the next dividend calendar event."""

    data_source = "yfinance"

    def fetch_next_dividend(self, ticker: str, as_of_date: datetime | None = None) -> dict | None:
        stock = yf.Ticker(ticker)
        calendar = stock.calendar
        if callable(calendar):
            calendar = calendar()
        try:
            info = stock.info or {}
        except Exception:
            info = {}

        payment_date = _normalize_optional_date(_calendar_lookup(calendar, ["Dividend Date", "Payment Date", "Pay Date"]))
        ex_dividend_date = _normalize_optional_date(_calendar_lookup(calendar, ["Ex-Dividend Date", "Ex Dividend Date"]))
        record_date = _normalize_optional_date(_calendar_lookup(calendar, ["Record Date"]))
        dividend_amount = _normalize_optional_number(
            _calendar_lookup(calendar, ["Dividend Amount", "Dividend Rate", "Dividend"])
        )

        if payment_date is None:
            return None

        if dividend_amount is None:
            dividend_amount = _latest_dividend_amount(stock, ex_dividend_date=ex_dividend_date)

        return {
            "ex_dividend_date": ex_dividend_date,
            "record_date": record_date,
            "payment_date": payment_date,
            "dividend_amount": dividend_amount,
            "currency": info.get("currency"),
            "data_source": self.data_source,
        }


class FMPDividendProvider(DividendProvider):
    """Financial Modeling Prep dividend provider."""

    data_source = "financial_modeling_prep"

    def __init__(self, api_key: str | None = None):
        _load_local_env_if_needed()
        self.api_key = api_key or os.getenv("FMP_API_KEY")

    def _fetch_json(self, ticker: str):
        import json
        from urllib.parse import urlencode
        from urllib.request import urlopen

        if not self.api_key:
            raise ValueError("FMP_API_KEY is not set")

        params = urlencode({"symbol": ticker, "apikey": self.api_key})
        url = f"https://financialmodelingprep.com/stable/dividends?{params}"
        with urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def fetch_next_dividend(self, ticker: str, as_of_date: datetime | None = None) -> dict | None:
        payload = self._fetch_json(ticker)
        if isinstance(payload, dict):
            payload = payload.get("historical") or payload.get("data") or payload.get("results") or []
        if not isinstance(payload, list) or not payload:
            return None

        as_of_timestamp = pd.Timestamp((as_of_date or datetime.today()).date())
        normalized_rows = []
        for row in payload:
            if not isinstance(row, dict):
                continue

            payment_date = _normalize_optional_date(_first_present(row, ["paymentDate", "payment_date", "payDate"]))
            if payment_date is None:
                continue

            payment_timestamp = pd.Timestamp(payment_date)
            if payment_timestamp < as_of_timestamp:
                continue

            dividend_amount = _normalize_optional_number(_first_present(
                row,
                ["dividend", "adjDividend", "adjustedDividend", "dividendAmount", "amount"],
            ))

            normalized_rows.append({
                "ex_dividend_date": _normalize_optional_date(_first_present(row, ["date", "exDividendDate", "ex_dividend_date"])),
                "record_date": _normalize_optional_date(_first_present(row, ["recordDate", "record_date"])),
                "payment_date": payment_date,
                "dividend_amount": dividend_amount,
                "currency": _first_present(row, ["currency", "reportedCurrency"]),
                "data_source": self.data_source,
            })

        if not normalized_rows:
            return None

        normalized_rows.sort(key=lambda item: item["payment_date"])
        return normalized_rows[0]


def _build_dividend_display_row(
    *,
    ticker: str,
    position_name: str,
    quantity,
    dividend_data: dict,
) -> dict:
    dividend_amount = dividend_data.get("dividend_amount")
    estimated_cash_dividend = None
    if quantity is not None and dividend_amount is not None:
        estimated_cash_dividend = float(quantity) * float(dividend_amount)

    return {
        "ticker": ticker,
        "position_name": position_name,
        "quantity": quantity,
        "ex_dividend_date": dividend_data.get("ex_dividend_date"),
        "payment_date": dividend_data.get("payment_date"),
        "dividend_amount": dividend_amount,
        "currency": dividend_data.get("currency"),
        "estimated_cash_dividend": estimated_cash_dividend,
        "data_source": dividend_data.get("data_source"),
    }


def display_upcoming_dividends(
    running_date: object = None,
    data_source: object = "ALL",
    provider: DividendProvider | None = None,
) -> pd.DataFrame:
    """Display current portfolio dividends payable in the current or next calendar month."""
    portfolio_context = _load_portfolio_context(running_date, data_source)
    if portfolio_context is None:
        return pd.DataFrame()

    running_date = portfolio_context["target_date"]
    current_positions = portfolio_context["current_positions"]
    market_ticker_map = portfolio_context["market_ticker_map"]
    window_start, window_end = _current_and_next_month_window(running_date)
    provider = provider or FMPDividendProvider()

    rows = []
    for position_name, position_data in current_positions.items():
        ticker = market_ticker_map.get(position_name)
        if not ticker:
            print(f"{position_name}: enum.csv 中没有 ticker mapping，跳过")
            continue

        try:
            dividend_data = provider.fetch_next_dividend(ticker, as_of_date=running_date)
        except Exception as e:
            print(f"警告: {ticker} dividend API 获取失败: {e}")
            continue

        if not dividend_data:
            continue

        payment_date = dividend_data.get("payment_date")
        if payment_date is None:
            continue

        payment_timestamp = pd.Timestamp(payment_date)
        if not (window_start <= payment_timestamp < window_end):
            continue

        rows.append(_build_dividend_display_row(
            ticker=ticker,
            position_name=position_name,
            quantity=position_data.get("position"),
            dividend_data=dividend_data,
        ))

    result_df = pd.DataFrame(rows)
    print(
        f"\nUpcoming dividends with payment date from "
        f"{window_start.strftime('%Y-%m-%d')} to {(window_end - pd.Timedelta(days=1)).strftime('%Y-%m-%d')}"
    )
    print("-" * 140)
    if result_df.empty:
        print("No current portfolio dividends found for current month or next month.")
        return result_df

    display_df = result_df.copy()
    for col in ["ex_dividend_date", "payment_date"]:
        display_df[col] = display_df[col].map(lambda x: "" if pd.isna(x) else str(x))
    for col in ["dividend_amount", "estimated_cash_dividend"]:
        display_df[col] = display_df[col].map(lambda x: "" if pd.isna(x) else f"{x:,.4f}")

    print(tabulate(
        display_df[
            [
                "ticker",
                "position_name",
                "quantity",
                "ex_dividend_date",
                "payment_date",
                "dividend_amount",
                "currency",
                "estimated_cash_dividend",
                "data_source",
            ]
        ],
        headers="keys",
        tablefmt="fancy_grid",
        showindex=False,
        disable_numparse=True,
    ))

    return result_df


def load_historical_pnl(target_date_str, data_source='ALL'):
    """加载指定日期的PnL数据"""
    try:
        # 转换日期格式
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
        formatted_date = target_date.strftime('%Y%m%d')

        # 设置文件路径
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        investment_dir = os.path.join(base_dir, 'investment')
        daily_pnl_dir = os.path.join(investment_dir, 'Daily Pnl')

        # 构建文件名模式
        if data_source == 'ALL':
            file_pattern = f'daily_pnl_SXAFI_SX9Q9_{formatted_date}.pkl'
        else:
            file_pattern = f'daily_pnl_{data_source}_{formatted_date}.pkl'

        pnl_file = os.path.join(daily_pnl_dir, file_pattern)

        if not os.path.exists(pnl_file):
            print(f"错误：找不到{target_date_str}的PnL数据文件")
            return

        # 读取pkl文件
        with open(pnl_file, 'rb') as f:
            daily_pnl_result = pickle.load(f)

        # 生成报告
        from . import generate_report

        market_details = daily_pnl_result['market_details']
        total_market_value = daily_pnl_result['total_market_value']
        total_cost = sum(data['cost'] for data in market_details)
        total_pnl = sum(data['pnl'] for data in market_details)
        realized_pnl = daily_pnl_result['realized_pnl']  # 历史数据中没有已实现盈亏信息
        regional_pnl = daily_pnl_result.get('regional_pnl')

        generate_report(market_details, total_market_value, total_pnl, total_cost, realized_pnl,
                        daily_pnl_result['date'], regional_pnl)

    except Exception as e:
        print(f"加载历史数据时发生错误: {e}")


def calculate_cumulative_contribution(start_date_str, end_date_str, data_source='ALL'):
    """计算指定日期范围内的累计贡献度和盈亏"""
    try:
        # 转换日期格式
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        date_range = pd.date_range(start=start_date, end=end_date)

        # 设置文件路径
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        investment_dir = os.path.join(base_dir, 'investment')
        daily_pnl_dir = os.path.join(investment_dir, 'Daily Pnl')

        # 存储每日数据
        daily_contributions = []
        daily_fx_contributions = []
        total_pnl = 0
        total_fx_pnl = 0
        total_non_fx_pnl = 0
        
        # 存储所有日期的数据
        all_daily_data = []

        # 定义指数列表
        indices = {
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
            "Bovespa (Brazil)": "^BVSP"
        }
        # 获取GBPUSD汇率数据
        try:
            gbpusd_ticker = yf.Ticker("GBPUSD=X")
            gbpusd_data = gbpusd_ticker.history(start=start_date - pd.Timedelta(days=1), end=end_date + pd.Timedelta(days=1))
            if not gbpusd_data.empty:
                gbpusd_start = gbpusd_data['Close'].iloc[0]
                gbpusd_end = gbpusd_data['Close'].iloc[-1]
                gbpusd_change = gbpusd_end - gbpusd_start
                gbpusd_bps = gbpusd_change * 10000
                print(f"\nGBP/USD汇率变化 ({start_date_str} 至 {end_date_str}):")
                print("-" * 60)
                print(f"起始汇率: {gbpusd_start:.4f}")
                print(f"结束汇率: {gbpusd_end:.4f}")
                print(f"汇率变化(bps): {gbpusd_bps:+.2f} bps")
                print("-" * 60)
            else:
                print("无法获取GBP/USD汇率数据")
        except Exception as e:
            print(f"获取GBP/USD汇率数据时发生错误: {e}")
        
        # 计算指数累计回报率
        index_returns = {}
        sp500_hist_data = pd.DataFrame()
        nasdaq_hist_data = pd.DataFrame()
        for index_name, ticker in indices.items():
            try:
                index = yf.Ticker(ticker)
                hist_data = index.history(start=start_date - pd.Timedelta(days=1), end=end_date + pd.Timedelta(days=1))
                if index_name == "S&P 500":
                    sp500_hist_data = hist_data.copy()
                if index_name == "Nasdaq 100":
                    nasdaq_hist_data = hist_data.copy()
                
                if len(hist_data.index) >= 2:
                    start_price = float(hist_data.loc[hist_data.index[0], 'Close'])
                    end_price = float(hist_data.loc[hist_data.index[-1], 'Close'])
                    total_return = ((end_price / start_price) - 1) * 100
                    index_returns[index_name] = total_return
                else:
                    index_returns[index_name] = None
            except Exception as e:
                print(f"获取{index_name}指数数据时发生错误: {e}")
                index_returns[index_name] = None

        print(f"\n{start_date_str}至{end_date_str}的盈亏分析:")
        print("-" * 120)
        print(f"{'日期':<12} {'当日贡献度(bps)':>15} {'当日总盈亏(GBP)':>15} {'当日外汇盈亏(GBP)':>15} "
              f"{'当日非外汇盈亏(GBP)':>15} {'当日总市值(GBP)':>15}")
        print("-" * 120)

        for date in date_range:
            formatted_date = date.strftime('%Y%m%d')

            # 构建文件名
            if data_source == 'ALL':
                file_pattern = f'daily_pnl_SXAFI_SX9Q9_{formatted_date}.pkl'
            else:
                file_pattern = f'daily_pnl_{data_source}_{formatted_date}.pkl'

            pnl_file = os.path.join(daily_pnl_dir, file_pattern)

            if os.path.exists(pnl_file):
                with open(pnl_file, 'rb') as f:
                    daily_pnl_result = pickle.load(f)

                if daily_pnl_result['total_market_value'] != 0:
                    contribution = (daily_pnl_result['total_daily_pnl'] / daily_pnl_result[
                        'total_market_value']) * 10000
                    daily_contributions.append(contribution)
                    fx_contribution = (daily_pnl_result['total_fx_pnl'] / daily_pnl_result[
                        'total_market_value']) * 10000
                    daily_fx_contributions.append(fx_contribution)

                    # 累计盈亏
                    total_pnl += daily_pnl_result['total_daily_pnl']
                    total_fx_pnl += daily_pnl_result['total_fx_pnl']
                    total_non_fx_pnl += daily_pnl_result['total_non_fx_pnl']
                    
                    # 存储每日数据
                    all_daily_data.append({
                        'date': date,
                        'contribution': contribution,
                        'fx_contribution': fx_contribution,
                        'total_daily_pnl': daily_pnl_result['total_daily_pnl'],
                        'total_fx_pnl': daily_pnl_result['total_fx_pnl'],
                        'total_non_fx_pnl': daily_pnl_result['total_non_fx_pnl'],
                        'total_market_value': daily_pnl_result['total_market_value']
                    })

        # 只显示最近10天的数据
        recent_data = all_daily_data[-10:] if len(all_daily_data) > 10 else all_daily_data
        
        # 打印最近10天的数据
        for data in recent_data:
            print(f"{data['date'].strftime('%Y-%m-%d'):<12} {data['contribution']:>15,.2f} "
                  f"{data['total_daily_pnl']:>15,.2f} "
                  f"{data['total_fx_pnl']:>20,.2f} "
                  f"{data['total_non_fx_pnl']:>20,.2f} "
                  f"{data['total_market_value']:>20,.2f}")

        print("-" * 120)
        if daily_contributions:
            cumulative_contribution = sum(daily_contributions)
            cumulative_fx_contribution = sum(daily_fx_contributions)
            days_held = (end_date - start_date).days
            T = days_held / 365.25
            annualized_return = ((1 + cumulative_contribution/10000) ** (1 / T) - 1) * 100# accounting for leap years
            contribution_series = pd.Series([data['contribution'] for data in all_daily_data]) / 10000
            fx_contribution_series = pd.Series([data['fx_contribution'] for data in all_daily_data]) / 10000
            annualization_factor = (len(all_daily_data) / T) ** 0.5
            annualized_contribution_vol = contribution_series.std() * annualization_factor * 100
            annualized_fx_contribution_vol = fx_contribution_series.std() * annualization_factor * 100

            contribution_plot_data = pd.DataFrame(all_daily_data).sort_values('date')
            contribution_plot_data['cumulative_return'] = (1 + contribution_plot_data['contribution'] / 10000).cumprod()
            contribution_plot_data['cumulative_return'] = (
                contribution_plot_data['cumulative_return'] / contribution_plot_data['cumulative_return'].iloc[0]
            )

            plt.figure(figsize=(12, 6))
            plt.plot(
                contribution_plot_data['date'],
                contribution_plot_data['cumulative_return'],
                label='Portfolio',
                linewidth=2
            )

            if not sp500_hist_data.empty:
                sp500_plot_data = sp500_hist_data.copy()
                sp500_plot_data.index = pd.to_datetime(sp500_plot_data.index).tz_localize(None)
                sp500_plot_data = sp500_plot_data[
                    (sp500_plot_data.index >= start_date) & (sp500_plot_data.index <= end_date)
                ].copy()
                if not sp500_plot_data.empty:
                    sp500_plot_data['cumulative_return'] = sp500_plot_data['Close'] / sp500_plot_data['Close'].iloc[0]
                    plt.plot(
                        sp500_plot_data.index,
                        sp500_plot_data['cumulative_return'],
                        label='S&P 500',
                        linewidth=2
                    )
                else:
                    print("指定日期范围内没有S&P 500数据，图中只显示Contribution Series")
            else:
                print("无法获取S&P 500数据，图中只显示Contribution Series")

            if not nasdaq_hist_data.empty:
                nasdaq_plot_data = nasdaq_hist_data.copy()
                nasdaq_plot_data.index = pd.to_datetime(nasdaq_plot_data.index).tz_localize(None)
                nasdaq_plot_data = nasdaq_plot_data[
                    (nasdaq_plot_data.index >= start_date) & (nasdaq_plot_data.index <= end_date)
                ].copy()
                if not nasdaq_plot_data.empty:
                    nasdaq_plot_data['cumulative_return'] = nasdaq_plot_data['Close'] / nasdaq_plot_data['Close'].iloc[0]
                    plt.plot(
                        nasdaq_plot_data.index,
                        nasdaq_plot_data['cumulative_return'],
                        label='NASDAQ',
                        linewidth=2
                    )
                else:
                    print("指定日期范围内没有NASDAQ数据，图中只显示Portfolio和S&P 500")
            else:
                print("无法获取NASDAQ数据，图中只显示Portfolio和S&P 500")

            plt.title(f"Cumulative Return ({start_date_str} to {end_date_str})")
            plt.xlabel("Date")
            plt.ylabel("Cumulative Return (Base = 1)")
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.show()

            print(f"\n汇总信息:")
            print("-" * 80)
            print(f"期间累计总贡献度: {cumulative_contribution:>15,.2f} bps")
            print(f"年化总贡献度: {annualized_return:>15,.2f}%")
            print(f"年化总贡献度波动率: {annualized_contribution_vol:>10,.2f}%")
            print(f"年化外汇贡献度波动率: {annualized_fx_contribution_vol:>8,.2f}%")
            print(f"期间外汇累计贡献度: {cumulative_fx_contribution:>12,.2f} bps")
            print(f"期间非外汇累计贡献度: {cumulative_contribution - cumulative_fx_contribution:>12,.2f} bps")
            print(f"期间总盈亏: {total_pnl:>20,.2f} GBP")
            print(f"期间外汇盈亏: {total_fx_pnl:>18,.2f} GBP")
            print(f"期间盈亏: {total_pnl - total_fx_pnl:>18,.2f} GBP")
            print("-" * 80)
            
            # 打印指数累计回报率
            print("\n全球主要指数累计回报率:")
            print("-" * 80)
            print(f"{'指数名称':<30} {'累计回报率(%)':>15}")
            print("-" * 80)
            for index_name, return_rate in sorted(index_returns.items(), key=lambda x: x[1] if x[1] is not None else float('-inf'), reverse=True):
                if return_rate is not None:
                    print(f"{index_name:<30} {return_rate:>15,.2f}")
                else:
                    print(f"{index_name:<30} {'N/A':>15}")
            print("-" * 80)
        else:
            print("在指定日期范围内没有找到数据")

    except Exception as e:
        print(f"计算累计贡献度时发生错误: {e}")


def run_historical_analysis(start_date_str='2025-01-01', end_date_str='2025-01-02'):
    """运行历史分析，从指定日期到今天之前的所有工作日"""
    try:
        # 转换日期格式
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        # end_date = datetime.today() - pd.Timedelta(days=1)  # 昨天
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

        # 生成工作日序列
        date_range = pd.date_range(start=start_date, end=end_date)
        business_days = [d for d in date_range if d.weekday() < 5]  # 排除周末

        # 数据源列表
        data_sources = ['ALL']

        print(f"\n开始运行从{start_date_str}到{end_date.strftime('%Y-%m-%d')}的历史分析")
        print("-" * 50)

        total_days = len(business_days)
        total_sources = len(data_sources)
        current_count = 0

        for date in business_days:
            date_str = date.strftime('%Y-%m-%d')
            for source in data_sources:
                current_count += 1
                progress = (current_count / (total_days * total_sources)) * 100
                print(f"\n处理日期: {date_str}, 数据源: {source} (总进度: {progress:.1f}%)")
                analyze_portfolio(date_str, source)

        print("\n历史分析完成！")
        print("-" * 50)

    except Exception as e:
        print(f"运行历史分析时发生错误: {e}")


def stock_monitor(days=30):
    """
    监控watchlist中的股票，计算指定天数的投资组合PnL
    
    Args:
        days: 要分析的天数，默认30天
    """
    import_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    watchlist_path = os.path.join(import_path, 'investment', 'watchlist.pkl')
    
    if not os.path.exists(watchlist_path):
        print("未找到watchlist.pkl，请先创建watchlist。")
        return
    
    # 读取watchlist分配
    with open(watchlist_path, 'rb') as f:
        stock_allocations = pickle.load(f)
    
    print(f"\n投资组合监控结果 (过去{days}天):")
    print("=" * 80)
    
    # 计算总名义金额
    total_notional = sum(data['notional_allocation'] for data in stock_allocations.values())
    print(f"总名义金额: {total_notional:,.2f}")
    print("=" * 80)
    
    # 存储每个股票的数据
    portfolio_data = {}
    total_pnl = 0
    total_return = 0
    
    # 获取GBPUSD汇率数据
    try:
        gbpusd_stock = yf.Ticker("GBPUSD=X")
        gbpusd_data = gbpusd_stock.history(start=(datetime.today() - pd.Timedelta(days=days + 1)), end=datetime.today())
        if not gbpusd_data.empty:
            gbpusd_start = gbpusd_data['Close'].iloc[0].item()
            gbpusd_end = gbpusd_data['Close'].iloc[-1].item()
            gbpusd_change = gbpusd_end - gbpusd_start
            gbpusd_return = (gbpusd_end / gbpusd_start - 1) * 100
            print(f"GBPUSD: {gbpusd_start:.4f} → {gbpusd_end:.4f} {gbpusd_change:>+8.4f} ({gbpusd_return:>+6.2f}%)")
        else:
            print("GBPUSD: 无法获取汇率数据")
    except Exception as e:
        print(f"GBPUSD: 获取汇率数据出错: {e}")
    
    print("-" * 80)
    
    for symbol, allocation_data in stock_allocations.items():
        try:
            # 获取历史价格数据
            stock = yf.Ticker(symbol)
            hist_data = stock.history(start=(datetime.today() - pd.Timedelta(days=days + 1)), end=datetime.today())
            
            # 计算价格变化
            start_price = hist_data['Close'].iloc[0].item()
            end_price = hist_data['Close'].iloc[-1].item()
            price_change = end_price - start_price
            price_return = (end_price / start_price - 1) * 100
            
            # 计算该股票的PnL
            stock_pnl = price_change * (allocation_data['notional_allocation'] / start_price)
            stock_return = price_return * allocation_data['weight']
            
            portfolio_data[symbol] = {
                'start_price': start_price,
                'end_price': end_price,
                'price_change': price_change,
                'price_return': price_return,
                'allocation': allocation_data['notional_allocation'],
                'weight': allocation_data['weight'],
                'pnl': stock_pnl,
                'return_contribution': stock_return
            }
            
            total_pnl += stock_pnl
            total_return += stock_return
            
            print(f"{symbol:<10} {start_price:>8.2f} → {end_price:>8.2f} "
                  f"{price_change:>+8.2f} ({price_return:>+6.2f}%) "
                  f"PnL: {stock_pnl:>10.2f} "
                  f"权重: {allocation_data['weight']:>6.3f}")
                  
        except Exception as e:
            print(f"{symbol:<10} 获取数据出错: {e}")
    
    print("=" * 80)
    print(f"投资组合总PnL: {total_pnl:>10.2f}")
    print(f"投资组合总回报: {total_return:>+6.2f}%")
    print(f"年化回报率: {(total_return / days * 365):>+6.2f}%")
    print("=" * 80)
    
    # 按PnL贡献排序
    if portfolio_data:
        print("\n按PnL贡献排序:")
        sorted_stocks = sorted(portfolio_data.items(), key=lambda x: x[1]['pnl'], reverse=True)
        print(f"{'股票':<10} {'PnL':<12} {'回报贡献':<12} {'权重':<8}")
        print("-" * 50)
        for symbol, data in sorted_stocks:
            print(f"{symbol:<10} {data['pnl']:<12.2f} {data['return_contribution']:<+12.2f}% {data['weight']:<8.3f}")
    
    return portfolio_data, total_pnl, total_return

def parse_ticker_db_date(path: Path) -> datetime:
    """从 tickers_NYSE+NASDAQ_20260514_171332.h5 解析 20260514"""
    m = re.search(r"_(\d{8})_\d{6}\.h5$", path.name)
    if not m:
        raise ValueError(f"无法从文件名解析日期: {path.name}")
    return datetime.strptime(m.group(1), "%Y%m%d")

def load_active_stock_universe(ticker_h5=None, as_of_date=None):
    ticker_db = OUTPUT_DIR / "tickers_NYSE+NASDAQ_20260519_165904.h5"
    h5_path = Path(ticker_h5) if ticker_h5 else ticker_db
    db_as_of = as_of_date or parse_ticker_db_date(h5_path)
    # read_h5 会打印摘要；若不想刷屏，可用下面静默版：
    tickers = pd.read_hdf(h5_path, key=H5_KEY)
    # tickers = read_h5(h5_path)
    # 通常只要上市、普通股
    universe = tickers[
        (tickers["status"] == "Active")
        & (tickers["asset_type"].str.upper() == "STOCK")
    ].copy()
    return universe, db_as_of, h5_path

def select_universe_symbols_by_industry(universe, yf_industry="Banks - Diversified"):
    universe_industry = universe[universe["yf_industry"] == yf_industry].copy()
    universe_industry = universe_industry[["symbol"]].copy()
    return universe_industry

def export_industry_price_returns(
    yf_industry="Banks - Diversified",
    ticker_h5=None,
    as_of_date=None,
    target_date=None,
    lookback_days=5,
    output_path=None,
    save_output=True,
):
    universe, db_as_of, h5_path = load_active_stock_universe(ticker_h5=ticker_h5, as_of_date=as_of_date)
    universe_industry = select_universe_symbols_by_industry(universe, yf_industry=yf_industry)
    if target_date is None:
        target_date = datetime.today()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d')
    start_date = target_date - pd.Timedelta(days=lookback_days)
    end_date = target_date + pd.Timedelta(days=1)
    all_history = []
    for ticker in universe_industry["symbol"].dropna().unique().tolist():
        try:
            stock = yf.Ticker(ticker)
            hist_data = stock.history(start=start_date, end=end_date)
            if hist_data.empty:
                print(f"{ticker}: no history data")
                continue
            hist_data = hist_data.copy()
            hist_data["symbol"] = ticker
            hist_data["daily_return"] = hist_data["Close"].pct_change()
            hist_data = hist_data.reset_index()
            all_history.append(hist_data)
        except Exception as e:
            print(f"{ticker}: failed to fetch history data: {e}")
    if all_history:
        price_returns = pd.concat(all_history, ignore_index=True)
    else:
        price_returns = pd.DataFrame(columns=["Date", "symbol", "Close", "daily_return"])
    if output_path is None:
        industry_slug = re.sub(r"[^A-Za-z0-9]+", "_", yf_industry).strip("_")
        output_path = OUTPUT_DIR / f"{industry_slug}_price_returns_{target_date.strftime('%Y%m%d')}.csv"
    else:
        output_path = Path(output_path)
    if save_output:
        price_returns.to_csv(output_path, index=False)
    print(f"Ticker universe as of {db_as_of.date()}: {len(universe):,} symbols from {h5_path}")
    print(f"{yf_industry}: {len(universe_industry):,} symbols")
    if save_output:
        print(f"Exported price returns to {output_path}")
    return universe_industry, price_returns, output_path

def analyze_portfolio_industry_percentiles(
    target_date=None,
    data_source='ALL',
    ticker_h5=None,
    as_of_date=None,
    lookback_days=5,
):
    """Calculate each current portfolio ticker's daily return percentile in its yf_industry."""
    portfolio_context = _load_portfolio_context(target_date, data_source)
    if portfolio_context is None:
        return pd.DataFrame()

    target_date = portfolio_context["target_date"]
    market_ticker_map = portfolio_context["market_ticker_map"]
    current_positions = portfolio_context["current_positions"]

    universe, db_as_of, h5_path = load_active_stock_universe(ticker_h5=ticker_h5, as_of_date=as_of_date)
    universe = universe.copy()
    universe["symbol_upper"] = universe["symbol"].astype(str).str.upper()

    portfolio_rows = []
    for market, position_data in current_positions.items():
        ticker = market_ticker_map.get(market)
        if not ticker:
            print(f"{market}: no ticker mapping in enum.csv")
            continue

        ticker_key = str(ticker).upper()
        ticker_row = universe[universe["symbol_upper"] == ticker_key]
        if ticker_row.empty:
            print(f"{ticker}: not found in {h5_path.name}")
            continue

        yf_industry = ticker_row["yf_industry"].iloc[0]
        if pd.isna(yf_industry) or not str(yf_industry).strip():
            print(f"{ticker}: no yf_industry in ticker database")
            continue

        portfolio_rows.append({
            "market": market,
            "ticker": ticker,
            "position": position_data.get("position"),
            "yf_industry": yf_industry,
        })

    if not portfolio_rows:
        print("No current portfolio positions matched to yf_industry.")
        return pd.DataFrame()

    portfolio_industries = sorted({row["yf_industry"] for row in portfolio_rows})
    industry_return_map = {}
    for yf_industry in portfolio_industries:
        _, price_returns, _ = export_industry_price_returns(
            yf_industry=yf_industry,
            ticker_h5=ticker_h5,
            as_of_date=as_of_date,
            target_date=target_date,
            lookback_days=lookback_days,
            save_output=False,
        )

        if price_returns.empty or "daily_return" not in price_returns.columns:
            print(f"{yf_industry}: no return data")
            continue

        date_col = "Date" if "Date" in price_returns.columns else "Datetime"
        price_returns = price_returns.dropna(subset=["daily_return"]).copy()
        if price_returns.empty:
            print(f"{yf_industry}: no valid daily_return data")
            continue

        price_returns[date_col] = pd.to_datetime(price_returns[date_col], utc=True).dt.tz_convert(None)
        latest_date = price_returns[date_col].max()
        latest_returns = price_returns[price_returns[date_col] == latest_date].copy()
        latest_returns["symbol_upper"] = latest_returns["symbol"].astype(str).str.upper()
        latest_returns = latest_returns.groupby("symbol_upper", as_index=False)["daily_return"].last()
        latest_returns["percentile"] = latest_returns["daily_return"].rank(pct=True, method="average") * 100

        industry_return_map[yf_industry] = {
            "latest_date": latest_date,
            "returns": latest_returns,
            "industry_size": len(latest_returns),
        }

    percentile_rows = []
    for row in portfolio_rows:
        industry_data = industry_return_map.get(row["yf_industry"])
        if not industry_data:
            continue

        ticker_key = str(row["ticker"]).upper()
        ticker_return_row = industry_data["returns"][industry_data["returns"]["symbol_upper"] == ticker_key]
        if ticker_return_row.empty:
            print(f"{row['ticker']}: no latest return found in {row['yf_industry']}")
            continue

        ticker_return_row = ticker_return_row.iloc[0]
        percentile_rows.append({
            "market": row["market"],
            "ticker": row["ticker"],
            "position": row["position"],
            "yf_industry": row["yf_industry"],
            "return_date": industry_data["latest_date"],
            "daily_return": ticker_return_row["daily_return"],
            "industry_percentile": ticker_return_row["percentile"],
            "industry_size": industry_data["industry_size"],
        })

    if not percentile_rows:
        print("No percentile results generated.")
        return pd.DataFrame()

    result_df = pd.DataFrame(percentile_rows).sort_values("industry_percentile", ascending=False)
    print(f"\nPortfolio industry return percentiles as of {target_date.strftime('%Y-%m-%d')}")
    print(f"Ticker universe as of {db_as_of.date()}: {len(universe):,} symbols from {h5_path}")
    print(tabulate(
        result_df.assign(
            daily_return=lambda df: df["daily_return"].map(lambda x: f"{x * 100:.2f}%"),
            industry_percentile=lambda df: df["industry_percentile"].map(lambda x: f"{x:.1f}%"),
        )[["ticker", "market", "yf_industry", "daily_return", "industry_percentile", "industry_size"]],
        headers="keys",
        tablefmt="fancy_grid",
        showindex=False,
    ))

    plot_df = result_df.sort_values("industry_percentile")
    colors = ["#2ca02c" if x >= 0 else "#d62728" for x in plot_df["daily_return"]]
    labels = plot_df["ticker"] + " | " + plot_df["yf_industry"]

    plt.figure(figsize=(12, max(6, len(plot_df) * 0.45)))
    plt.barh(labels, plot_df["industry_percentile"], color=colors)
    plt.xlim(0, 100)
    plt.xlabel("Industry Daily Return Percentile")
    plt.title(f"Portfolio Ticker Percentile vs Industry ({target_date.strftime('%Y-%m-%d')})")
    plt.grid(axis="x", alpha=0.3)
    for i, value in enumerate(plot_df["industry_percentile"]):
        plt.text(min(value + 1, 98), i, f"{value:.1f}%", va="center")
    plt.tight_layout()
    plt.show()

    return result_df

def stock_value_factor(ticker_h5=None, as_of_date=None, fiscal_year=2025, fiscal_period="q4", limit=None):
    ticker_db = OUTPUT_DIR / "tickers_NYSE+NASDAQ_20260519_165904.h5"
    h5_path = ticker_h5 or ticker_db
    db_as_of = as_of_date or parse_ticker_db_date(h5_path)
    # read_h5 会打印摘要；若不想刷屏，可用下面静默版：
    tickers = pd.read_hdf(h5_path, key=H5_KEY)
    # tickers = read_h5(h5_path)
    # 通常只要上市、普通股
    universe = tickers[
        (tickers["status"] == "Active")
        & (tickers["asset_type"].str.upper() == "STOCK")
    ].copy()
    print(f"Ticker universe as of {db_as_of.date()}: {len(universe):,} symbols")
    symbols = universe["symbol"].tolist()
    earnings_df = fetch_earnings_batch(
        symbols,
        year=fiscal_year,
        period=fiscal_period,
        limit=limit,  # 全市场先别去掉 limit
        sleep_sec=0.25,  # 按你套餐调，避免 429
    )
    # 后续：对 universe["symbol"] 拉估值/earnings（如 API Ninjas）再算 value factor
    return universe, db_as_of, earnings_df



if __name__ == "__main__":
    # 测试分析功能
    print("测试分析模块")

    # 测试投资组合分析
    print("\n1. 测试当前投资组合分析")
    analyze_portfolio(data_source='ALL')

    # 测试历史PnL加载
    print("\n2. 测试历史PnL加载")
    load_historical_pnl('2025-02-28', data_source='ALL')

    # 测试累计贡献度计算
    print("\n3. 测试累计贡献度计算")
    calculate_cumulative_contribution('2025-02-19', '2025-02-28', data_source='ALL')

    # 测试历史分析
    print("\n4. 测试历史分析")
    run_historical_analysis('2025-02-19') 
