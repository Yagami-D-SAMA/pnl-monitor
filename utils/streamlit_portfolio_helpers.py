from __future__ import annotations

import pickle
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd
import streamlit as st

from .portfolio_aggregation import aggregate_holdings_by_strategy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRADE_DISPLAY_COLUMNS = [
    "TextDate",
    "Time",
    "Activity",
    "Market",
    "Direction",
    "Quantity",
    "Price",
    "Currency",
    "Consideration",
    "Commission",
    "Charges",
    "Cost/Proceeds",
    "Conversion rate",
    "Order type",
    "Venue ID",
    "Settlement date",
    "Order ID",
    "AssetType",
    "Region",
    "Strategy",
]

def get_expected_pnl_file(data_source: str, target_date: object) -> Path:
    source_map = {
        "ALL": "SXAFI_SX9Q9",
        "SXAFI": "SXAFI",
        "SX9Q9": "SX9Q9",
    }
    source_prefix = source_map[data_source]
    date_tag = target_date.strftime("%Y%m%d")
    return PROJECT_ROOT / "investment" / "Daily Pnl" / f"daily_pnl_{source_prefix}_{date_tag}.pkl"


def run_portfolio_analysis_in_process(
    target_date: object,
    data_source: str = "ALL",
    asset_type: bool = True,
    save_results: bool = False,
) -> tuple[int, str, object | None]:
    """
    Run analyze_portfolio() inside Streamlit and capture everything printed by
    generate_report(), plus the surrounding analyzer output.
    """
    buffer = StringIO()
    try:
        from utils.analyzer import analyze_portfolio

        with redirect_stdout(buffer), redirect_stderr(buffer):
            result = analyze_portfolio(
                target_date.strftime("%Y-%m-%d"),
                data_source=data_source,
                asset_type=asset_type,
                prompt_for_constituents=False,
                save_results=save_results,
            )
        return 0, buffer.getvalue(), result
    except Exception as exc:
        print(f"Streamlit wrapper error: {exc}", file=buffer)
        return 1, buffer.getvalue(), None


def save_pending_daily_pnl(pending_result: object, overwrite_existing: bool) -> tuple[int, str]:
    buffer = StringIO()
    try:
        with redirect_stdout(buffer), redirect_stderr(buffer):
            pending_result["data_loader"].save_results(
                pending_result["daily_pnl_result"],
                pending_result["trade_history_paths"],
                overwrite_existing=overwrite_existing,
            )
        return 0, buffer.getvalue()
    except Exception as exc:
        print(f"Streamlit save error: {exc}", file=buffer)
        return 1, buffer.getvalue()


def aggregate_market_details(
    market_details: list[dict],
    group_key: str,
    value_key: str,
    fallback_key: str | None = None,
) -> dict:
    values = {}
    for detail in market_details:
        group_name = detail.get(group_key)
        if (group_name is None or pd.isna(group_name)) and fallback_key:
            group_name = detail.get(fallback_key)
        if group_name is None or pd.isna(group_name):
            continue
        values[group_name] = values.get(group_name, 0) + (detail.get(value_key) or 0)
    return values


def build_historical_analysis_result(daily_pnl_result: dict) -> dict:
    market_details = daily_pnl_result.get("market_details") or []
    total_market_value = daily_pnl_result.get("total_market_value") or 0
    total_cost = sum(detail.get("cost") or 0 for detail in market_details)
    total_pnl = sum(detail.get("pnl") or 0 for detail in market_details)
    realized_pnl = daily_pnl_result.get("realized_pnl") or 0

    current_positions = {
        detail.get("market"): {
            "position": detail.get("position"),
            "ccy": "N/A",
            "strategy": detail.get("Strategy"),
        }
        for detail in market_details
        if detail.get("market")
    }

    return {
        "daily_pnl_result": daily_pnl_result,
        "target_date": daily_pnl_result.get("date"),
        "trades_df": pd.DataFrame(),
        "current_positions": current_positions,
        "market_ticker_map": {},
        "portfolio_summary": {
            "total_market_value": total_market_value,
            "total_cost": total_cost,
            "total_pnl": total_pnl,
            "realized_pnl": realized_pnl,
            "total_pnl_including_realized": total_pnl + realized_pnl,
        },
        "region_pnl": daily_pnl_result.get("regional_pnl")
        or aggregate_market_details(market_details, "region", "daily_pnl"),
        "strategy_pnl": aggregate_market_details(market_details, "Strategy", "daily_pnl", fallback_key="market"),
        "region_market_value": aggregate_market_details(market_details, "region", "market_value"),
        "strategy_market_value": aggregate_market_details(
            market_details,
            "Strategy",
            "market_value",
            fallback_key="market",
        ),
    }


def load_historical_pnl_in_process(target_date: object, data_source: str) -> tuple[int, str, object | None, Path]:
    buffer = StringIO()
    pnl_file = get_expected_pnl_file(data_source, target_date)
    try:
        if not pnl_file.exists():
            print(f"错误：找不到{target_date.strftime('%Y-%m-%d')}的PnL数据文件: {pnl_file}", file=buffer)
            return 1, buffer.getvalue(), None, pnl_file

        with open(pnl_file, "rb") as file:
            daily_pnl_result = pickle.load(file)

        analysis_result = build_historical_analysis_result(daily_pnl_result)
        market_details = daily_pnl_result.get("market_details") or []
        with redirect_stdout(buffer), redirect_stderr(buffer):
            print(f"Loaded historical PnL file: {pnl_file}")
            if market_details:
                from utils.report_generator import generate_report

                total_market_value = daily_pnl_result.get("total_market_value") or 0
                generate_report(
                    market_details,
                    total_market_value,
                    analysis_result["portfolio_summary"]["total_pnl"],
                    analysis_result["portfolio_summary"]["total_cost"],
                    analysis_result["portfolio_summary"]["realized_pnl"],
                    daily_pnl_result.get("date"),
                    analysis_result.get("region_pnl"),
                    analysis_result.get("region_market_value"),
                    analysis_result.get("strategy_pnl"),
                    analysis_result.get("strategy_market_value"),
                )
        return 0, buffer.getvalue(), analysis_result, pnl_file
    except Exception as exc:
        print(f"加载历史PnL时发生错误: {exc}", file=buffer)
        return 1, buffer.getvalue(), None, pnl_file


def build_position_options(pending_result: object) -> list[str]:
    current_positions = pending_result.get("current_positions") or {}
    if current_positions:
        return list(current_positions)

    daily_pnl_result = pending_result.get("daily_pnl_result") or {}
    market_details = daily_pnl_result.get("market_details") or []
    return list(dict.fromkeys(
        row["market"] for row in market_details if row.get("market")
    ))


def get_position_trade_history(pending_result: object, market: str):
    trades_df = pending_result.get("trades_df")
    if trades_df is None or trades_df.empty:
        return None

    position_trades = trades_df[trades_df["Market"] == market].copy()
    if position_trades.empty:
        return position_trades

    position_trades = position_trades.sort_values(["TextDate", "Time"], ascending=[False, False])
    display_columns = [column for column in TRADE_DISPLAY_COLUMNS if column in position_trades.columns]
    position_trades = position_trades[display_columns]
    if "TextDate" in position_trades.columns:
        position_trades["TextDate"] = position_trades["TextDate"].dt.strftime("%Y-%m-%d")
    return position_trades


def get_position_trade_history_for_chart(pending_result: object, market: str) -> pd.DataFrame:
    trades_df = pending_result.get("trades_df")
    if trades_df is None or trades_df.empty:
        return pd.DataFrame()

    position_trades = trades_df[trades_df["Market"] == market].copy()
    if position_trades.empty:
        return position_trades

    position_trades["TextDate"] = pd.to_datetime(position_trades["TextDate"], errors="coerce")
    position_trades = position_trades.dropna(subset=["TextDate"])
    if "Activity" in position_trades.columns:
        activity = position_trades["Activity"].astype(str).str.strip().str.upper()
        position_trades = position_trades[
            ~activity.str.contains("CORPORATE", na=False)
        ]
    if "Direction" in position_trades.columns:
        position_trades = position_trades[
            position_trades["Direction"].astype(str).str.upper().isin(["BUY", "SELL"])
        ]
    return position_trades


def get_split_adjustment_factor(splits: pd.Series, trade_date: object, end_date: object) -> float:
    if splits is None or splits.empty:
        return 1.0

    split_dates = pd.to_datetime(splits.index).tz_localize(None)
    trade_timestamp = pd.Timestamp(trade_date).tz_localize(None)
    end_timestamp = pd.Timestamp(end_date).tz_localize(None)
    relevant_splits = splits[(split_dates > trade_timestamp) & (split_dates <= end_timestamp)]
    if relevant_splits.empty:
        return 1.0
    return float(relevant_splits.prod())


def build_trade_marker_df(
    trades_df: pd.DataFrame,
    splits: pd.Series,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    if trades_df is None or trades_df.empty:
        return pd.DataFrame()

    plot_trades = trades_df[
        (trades_df["TextDate"] >= start_date) & (trades_df["TextDate"] <= end_date)
    ].copy()
    if plot_trades.empty:
        return plot_trades

    plot_trades["QuantityAbs"] = pd.to_numeric(plot_trades["Quantity"], errors="coerce").abs()
    plot_trades["Price"] = pd.to_numeric(plot_trades["Price"], errors="coerce")
    plot_trades = plot_trades.dropna(subset=["QuantityAbs", "Price"])
    if plot_trades.empty:
        return plot_trades

    plot_trades["DirectionUpper"] = plot_trades["Direction"].astype(str).str.upper()
    plot_trades["SplitFactor"] = plot_trades["TextDate"].map(
        lambda trade_date: get_split_adjustment_factor(splits, trade_date, end_date)
    )
    plot_trades["AdjustedPrice"] = plot_trades["Price"] / plot_trades["SplitFactor"]
    max_quantity = plot_trades["QuantityAbs"].max()
    if max_quantity and max_quantity > 0:
        size_scale = (plot_trades["QuantityAbs"] / max_quantity).pow(1.6)
        plot_trades["MarkerSize"] = 10 + size_scale * 340
    else:
        plot_trades["MarkerSize"] = 45
    return plot_trades


def get_trade_label_offset(index: int, direction: str) -> tuple[int, int]:
    x_offsets = [-10, 0, 10, -18, 18, 0]
    buy_offsets = [18, 34, 50, 66, 82, 98]
    sell_offsets = [-22, -38, -54, -70, -86, -102]
    y_offsets = buy_offsets if direction == "BUY" else sell_offsets
    return x_offsets[index % len(x_offsets)], y_offsets[index % len(y_offsets)]


def format_trade_marker_label(trade: pd.Series) -> str:
    direction = str(trade.get("Direction", "")).upper()
    direction_label = "BUY" if direction == "BUY" else "SELL" if direction == "SELL" else direction[:1]
    try:
        quantity = abs(float(trade.get("Quantity", 0)))
        quantity_label = f"{quantity:,.0f}"
    except (TypeError, ValueError):
        quantity_label = str(trade.get("Quantity", ""))

    try:
        price = float(trade.get("AdjustedPrice", trade.get("Price", 0)))
        price_label = f"{price:,.2f}"
    except (TypeError, ValueError):
        price_label = str(trade.get("AdjustedPrice", trade.get("Price", "")))

    return f"{direction_label}\nSize {quantity_label}\nPrice {price_label}".strip()


def get_trade_label_color(direction: str) -> str:
    if direction == "BUY":
        return "darkgreen"
    if direction == "SELL":
        return "darkred"
    return "dimgray"


def plot_position_price_history(
    ticker: str,
    market: str,
    trades_df: pd.DataFrame,
    years: int,
    end_date: object,
):
    import matplotlib.pyplot as plt
    import yfinance as yf

    end_timestamp = pd.Timestamp(end_date).tz_localize(None)
    start_timestamp = end_timestamp - pd.DateOffset(years=years)
    stock = yf.Ticker(ticker)
    history = stock.history(
        start=start_timestamp.strftime("%Y-%m-%d"),
        end=(end_timestamp + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        auto_adjust=True,
    )
    if history.empty or "Close" not in history.columns:
        return None, f"{ticker}: no price history available for past {years} year(s)."

    price_history = history.copy()
    price_history.index = pd.to_datetime(price_history.index).tz_localize(None)
    price_history = price_history[(price_history.index >= start_timestamp) & (price_history.index <= end_timestamp)]
    if price_history.empty:
        return None, f"{ticker}: no price history in selected date window."

    try:
        splits = stock.splits
        if splits is not None and not splits.empty:
            splits.index = pd.to_datetime(splits.index).tz_localize(None)
    except Exception:
        splits = pd.Series(dtype=float)

    marker_df = build_trade_marker_df(trades_df, splits, start_timestamp, end_timestamp)
    if not marker_df.empty:
        history_median = pd.to_numeric(price_history["Close"], errors="coerce").dropna().median()
        trade_median = pd.to_numeric(marker_df["AdjustedPrice"], errors="coerce").dropna().median()
        if pd.notna(history_median) and pd.notna(trade_median) and trade_median:
            if history_median / trade_median > 20:
                price_history["Close"] = price_history["Close"] / 100

    figure, axis = plt.subplots(figsize=(11, 5))
    axis.plot(price_history.index, price_history["Close"], color="blue", linewidth=1.6, label="Price")

    if not marker_df.empty:
        axis.scatter(
            marker_df["TextDate"],
            marker_df["AdjustedPrice"],
            s=marker_df["MarkerSize"],
            color="red",
            alpha=0.7,
            edgecolors="white",
            linewidths=0.8,
            label="Buy/Sell trades",
            zorder=3,
        )
        label_trades = marker_df.sort_values("TextDate").reset_index(drop=True)
        for label_index, trade in label_trades.iterrows():
            direction = str(trade.get("DirectionUpper", trade.get("Direction", ""))).upper()
            label = format_trade_marker_label(trade)
            x_offset, y_offset = get_trade_label_offset(label_index, direction)
            label_color = get_trade_label_color(direction)
            axis.annotate(
                label,
                (trade["TextDate"], trade["AdjustedPrice"]),
                textcoords="offset points",
                xytext=(x_offset, y_offset),
                ha="center",
                va="center",
                fontsize=7,
                color=label_color,
                bbox={
                    "boxstyle": "round,pad=0.18",
                    "facecolor": "white",
                    "edgecolor": label_color,
                    "linewidth": 0.5,
                    "alpha": 0.86,
                },
                arrowprops={
                    "arrowstyle": "-",
                    "color": label_color,
                    "alpha": 0.45,
                    "linewidth": 0.6,
                },
            )

    axis.set_title(f"{market} ({ticker}) price history - past {years}Y")
    axis.set_xlabel("Date")
    axis.set_ylabel("Adjusted price")
    axis.grid(True, alpha=0.25)
    axis.legend(loc="best")
    figure.autofmt_xdate()
    return figure, ""


def display_position_price_history_charts(
    ticker: str,
    market: str,
    analysis_result: object,
    end_date: object,
) -> None:
    if not ticker:
        st.info("No ticker mapping is available for this position.")
        return

    chart_trades = get_position_trade_history_for_chart(analysis_result, market)
    chart_tabs = st.tabs(["1Y", "2Y", "3Y", "5Y"])
    for tab, years in zip(chart_tabs, [1, 2, 3, 5], strict=True):
        with tab:
            with st.spinner(f"Loading {ticker} {years}Y price history..."):
                figure, message = plot_position_price_history(
                    ticker=ticker,
                    market=market,
                    trades_df=chart_trades,
                    years=years,
                    end_date=end_date,
                )
            if message:
                st.warning(message)
            if figure is not None:
                st.pyplot(figure, use_container_width=True)


def build_cumulative_return_chart_data(figure: object) -> dict[str, object] | None:
    """Extract cumulative chart series from an analyzer Matplotlib figure."""
    axes = getattr(figure, "axes", [])
    if not axes:
        return None

    records: list[dict[str, object]] = []
    for line in axes[0].get_lines():
        series_name = str(line.get_label())
        if not series_name or series_name.startswith("_"):
            continue

        dates = pd.to_datetime(line.get_xdata(), errors="coerce")
        values = pd.to_numeric(pd.Series(line.get_ydata()), errors="coerce")
        for chart_date, value in zip(dates, values, strict=False):
            if pd.isna(chart_date) or pd.isna(value):
                continue
            records.append(
                {
                    "date": pd.Timestamp(chart_date).isoformat(),
                    "series": series_name,
                    "cumulative_return": float(value),
                }
            )

    if not records:
        return None

    y_axis_title = axes[0].get_ylabel() or "Cumulative Return (Base = 1)"
    is_currency_chart = "GBP" in y_axis_title.upper()
    return {
        "title": axes[0].get_title() or "Cumulative Return",
        "y_axis_title": y_axis_title,
        "value_format": ",.2f" if is_currency_chart else ".4f",
        "include_zero": is_currency_chart,
        "records": records,
    }


def display_cumulative_return_chart(chart_data: dict[str, object]) -> None:
    """Display cumulative series with a shared tooltip and vertical crosshair."""
    chart_type = chart_data.get("chart_type")
    if chart_type == "daily_contribution_table":
        display_daily_contribution_table(chart_data)
        return
    if chart_type == "percentile_comparison":
        display_performance_percentile_chart(chart_data)
        return

    import altair as alt

    records = chart_data.get("records", [])
    if not records:
        return

    long_data = pd.DataFrame(records)
    long_data["date"] = pd.to_datetime(long_data["date"], errors="coerce")
    long_data["cumulative_return"] = pd.to_numeric(
        long_data["cumulative_return"],
        errors="coerce",
    )
    long_data = long_data.dropna(subset=["date", "series", "cumulative_return"])
    if long_data.empty:
        return

    series_order = [
        name
        for name in ["Portfolio", "S&P 500", "NASDAQ"]
        if name in long_data["series"].unique()
    ]
    series_order.extend(
        name for name in long_data["series"].unique() if name not in series_order
    )
    y_axis_title = str(
        chart_data.get("y_axis_title", "Cumulative Return (Base = 1)")
    )
    value_format = str(chart_data.get("value_format", ".4f"))
    include_zero = bool(chart_data.get("include_zero", False))

    wide_data = (
        long_data.pivot_table(
            index="date",
            columns="series",
            values="cumulative_return",
            aggfunc="last",
        )
        .reindex(columns=series_order)
        .sort_index()
        .ffill()
        .reset_index()
    )

    date_values = wide_data["date"].tolist()
    if len(date_values) == 1:
        hover_starts = [date_values[0] - pd.Timedelta(hours=12)]
        hover_ends = [date_values[0] + pd.Timedelta(hours=12)]
    else:
        date_midpoints = [
            left_date + (right_date - left_date) / 2
            for left_date, right_date in zip(
                date_values[:-1],
                date_values[1:],
                strict=True,
            )
        ]
        hover_starts = [
            date_values[0] - (date_midpoints[0] - date_values[0]),
            *date_midpoints,
        ]
        hover_ends = [
            *date_midpoints,
            date_values[-1] + (date_values[-1] - date_midpoints[-1]),
        ]

    hover_data = wide_data.copy()
    hover_data["hover_start"] = hover_starts
    hover_data["hover_end"] = hover_ends

    selected_date = alt.selection_point(
        fields=["date"],
        on="pointerover",
        empty=False,
    )
    date_span_days = (date_values[-1] - date_values[0]).days
    date_label_format = "%d-%b-%y" if date_span_days <= 120 else "%b-%y"
    date_tick_count = "week" if date_span_days <= 120 else "month"
    date_axis = alt.Axis(
        format=date_label_format,
        tickCount=date_tick_count,
        labelAngle=-45,
        labelAlign="right",
        labelBaseline="middle",
        labelOverlap="greedy",
        labelPadding=6,
        titlePadding=55,
    )
    base = alt.Chart(wide_data).encode(
        x=alt.X("date:T", title="Date", axis=date_axis)
    )
    benchmark_colors = {
        "Portfolio": "#1f77b4",
        "S&P 500": "#d62728",
        "NASDAQ": "#2ca02c",
    }
    if all(series in benchmark_colors for series in series_order):
        color_scale = alt.Scale(
            domain=series_order,
            range=[benchmark_colors[series] for series in series_order],
        )
    else:
        color_scale = alt.Scale(domain=series_order, scheme="tableau20")

    series_lines = (
        base.transform_fold(series_order, as_=["series", "cumulative_return"])
        .mark_line(strokeWidth=2)
        .encode(
            y=alt.Y(
                "cumulative_return:Q",
                title=y_axis_title,
                scale=alt.Scale(zero=include_zero),
            ),
            color=alt.Color(
                "series:N",
                title=None,
                sort=series_order,
                scale=color_scale,
            ),
        )
    )
    points = series_lines.mark_point(size=65).encode(
        opacity=alt.condition(selected_date, alt.value(1), alt.value(0))
    )
    lines = series_lines
    if len(series_order) > 3:
        selected_series = alt.selection_point(
            fields=["series"],
            bind="legend",
        )
        lines = lines.encode(
            opacity=alt.condition(
                selected_series,
                alt.value(1.0),
                alt.value(0.15),
            ),
            strokeWidth=alt.condition(
                selected_series,
                alt.value(4.0),
                alt.value(1.25),
            ),
        ).add_params(selected_series)
    tooltip_fields = [alt.Tooltip("date:T", title="Date", format="%Y-%m-%d")]
    tooltip_fields.extend(
        alt.Tooltip(f"{series}:Q", title=series, format=value_format)
        for series in series_order
    )
    crosshair = (
        base.transform_filter(selected_date)
        .mark_rule(color="#808080", strokeWidth=1)
    )
    selectors = (
        alt.Chart(hover_data)
        .mark_rect(opacity=0)
        .encode(
            x=alt.X("hover_start:T", title="Date", axis=date_axis),
            x2="hover_end:T",
            tooltip=tooltip_fields,
        )
        .add_params(selected_date)
    )

    chart = (
        alt.layer(lines, points, crosshair, selectors)
        .properties(
            title=str(chart_data.get("title", "Cumulative Return")),
            height=500,
            padding={"left": 5, "top": 5, "right": 5, "bottom": 55},
        )
        .configure_axis(grid=True, gridOpacity=0.2)
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(chart, use_container_width=True)


def build_daily_contribution_display_frame(
    records: list[dict[str, object]],
) -> pd.DataFrame:
    """Build the browser-rendered daily contribution table."""
    columns = {
        "date": "日期",
        "contribution": "当日贡献度(bps)",
        "sp500_contribution": "当日贡献度 SPX(bps)",
        "nasdaq_contribution": "当日贡献度 NASDAQ(bps)",
        "total_daily_pnl": "当日总盈亏(GBP)",
        "total_fx_pnl": "当日外汇盈亏(GBP)",
        "total_non_fx_pnl": "当日非外汇盈亏(GBP)",
        "total_market_value": "当日总市值(GBP)",
    }
    if not records:
        return pd.DataFrame(columns=list(columns.values()))

    frame = pd.DataFrame(records).reindex(columns=list(columns))
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in list(columns)[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.rename(columns=columns)


def display_daily_contribution_table(chart_data: dict[str, object]) -> None:
    """Render daily contribution records using Streamlit's native grid layout."""
    records = chart_data.get("records", [])
    frame = build_daily_contribution_display_frame(records)
    if frame.empty:
        return

    st.markdown(f"### {chart_data.get('title', '日度盈亏分析')}")
    numeric_columns = list(frame.columns[1:])
    column_config = {
        "日期": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
        **{
            column: st.column_config.NumberColumn(column, format="%,.2f")
            for column in numeric_columns
        },
    }
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )


def display_performance_percentile_chart(
    chart_data: dict[str, object],
) -> None:
    """Display portfolio and index performance percentiles as a heatmap."""
    import altair as alt

    records = chart_data.get("records", [])
    comparison = pd.DataFrame(records)
    required_columns = {
        "asset",
        "metric",
        "value_pct",
        "percentile",
        "rank",
        "universe_size",
        "is_portfolio",
    }
    if comparison.empty or not required_columns.issubset(comparison.columns):
        return

    numeric_columns = ["value_pct", "percentile", "rank", "universe_size"]
    for column in numeric_columns:
        comparison[column] = pd.to_numeric(comparison[column], errors="coerce")
    comparison = comparison.dropna(subset=numeric_columns)
    if comparison.empty:
        return

    comparison["cell_label"] = comparison.apply(
        lambda row: f"{row['percentile']:.0f} | #{int(row['rank'])}",
        axis=1,
    )
    metric_order = ["期间累计回报", "今年最大回撤", "年化波动率"]
    asset_scores = (
        comparison.groupby("asset", sort=False)["percentile"].mean().sort_values(
            ascending=False
        )
    )
    asset_order = ["Portfolio"] if "Portfolio" in asset_scores.index else []
    asset_order.extend(
        asset for asset in asset_scores.index if asset != "Portfolio"
    )

    base = alt.Chart(comparison).encode(
        x=alt.X(
            "metric:N",
            title=None,
            sort=metric_order,
            axis=alt.Axis(labelAngle=0, labelPadding=8),
        ),
        y=alt.Y(
            "asset:N",
            title=None,
            sort=asset_order,
            axis=alt.Axis(labelLimit=260),
        ),
    )
    heatmap = base.mark_rect(cornerRadius=2).encode(
        color=alt.Color(
            "percentile:Q",
            title="Percentile",
            scale=alt.Scale(
                domain=[0, 50, 100],
                range=["#b91c1c", "#f59e0b", "#15803d"],
            ),
        ),
        tooltip=[
            alt.Tooltip("asset:N", title="Asset"),
            alt.Tooltip("metric:N", title="Metric"),
            alt.Tooltip("value_pct:Q", title="Actual (%)", format=".2f"),
            alt.Tooltip("percentile:Q", title="Percentile", format=".1f"),
            alt.Tooltip("rank:Q", title="Rank", format=".0f"),
            alt.Tooltip("universe_size:Q", title="Universe", format=".0f"),
        ],
    )
    labels = base.mark_text(fontSize=12, fontWeight="bold").encode(
        text=alt.Text("cell_label:N"),
        color=alt.condition(
            "datum.percentile >= 65 || datum.percentile <= 30",
            alt.value("white"),
            alt.value("#111827"),
        ),
    )
    portfolio_outline = (
        base.transform_filter("datum.is_portfolio")
        .mark_rect(fillOpacity=0, stroke="#38bdf8", strokeWidth=3)
    )
    chart = (
        alt.layer(heatmap, portfolio_outline, labels)
        .properties(
            title=(
                "Portfolio vs Global Indices Percentile Comparison "
                "(higher = better)"
            ),
            height=max(360, len(asset_order) * 31),
        )
        .configure_axis(grid=False)
        .configure_view(strokeWidth=0)
    )
    st.caption(
        "累计回报越高、最大回撤越接近0、年化波动率越低，Percentile越高。"
        "单元格显示 Percentile | 排名；Portfolio 使用蓝色边框突出。"
    )
    st.altair_chart(chart, use_container_width=True)


def extract_market_value_messages(output: str) -> list[str]:
    """Pull calculation warnings from captured calculate_market_values output."""
    if not output:
        return []

    message_markers = [
        "没有",
        "不足2天",
        "发生错误",
        "Alpha Vantage",
        "限流",
        "错误",
        "警告",
    ]
    calculation_context_markers = [
        "价格数据",
        "数据时",
        "行情",
        "日线数据",
        "Alpha Vantage",
        "yfinance",
    ]
    messages = []
    seen = set()
    for line in output.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        has_message_marker = any(marker in cleaned for marker in message_markers)
        has_calculation_context = any(marker in cleaned for marker in calculation_context_markers)
        if has_message_marker and has_calculation_context and cleaned not in seen:
            messages.append(cleaned)
            seen.add(cleaned)
    return messages


def display_market_value_messages(output: str) -> None:
    messages = extract_market_value_messages(output)
    if not messages:
        return

    st.markdown("### 价格数据提示")
    for message in messages:
        if "发生错误" in message or "错误" in message or "限流" in message:
            st.warning(message)
        else:
            st.info(message)


def build_number_column_config(
    df: pd.DataFrame,
    percent_columns: set[str] | None = None,
    number_formats: dict[str, str] | None = None,
) -> dict:
    percent_columns = percent_columns or set()
    number_formats = number_formats or {}
    column_config = {}
    for column in df.columns:
        if column in number_formats and pd.api.types.is_numeric_dtype(df[column]):
            column_config[column] = st.column_config.NumberColumn(
                format=number_formats[column]
            )
        elif column in percent_columns:
            column_config[column] = st.column_config.NumberColumn(format="%.2f%%")
        elif pd.api.types.is_numeric_dtype(df[column]):
            column_config[column] = st.column_config.NumberColumn(format="%,.2f")
    return column_config


def build_holdings_table(analysis_result: object) -> pd.DataFrame:
    daily_pnl_result = analysis_result.get("daily_pnl_result") or {}
    market_details = daily_pnl_result.get("market_details") or []
    total_market_value = daily_pnl_result.get("total_market_value") or 0
    rows = []

    for detail in market_details:
        cost = detail.get("cost") or 0
        market_value = detail.get("market_value") or 0
        standalone_return = (detail.get("pnl") or 0) / abs(cost) if cost else 0
        market_value_pct = market_value / total_market_value if total_market_value else 0
        rows.append({
            "Market": detail.get("market"),
            "Ticker": analysis_result.get("market_ticker_map", {}).get(detail.get("market"), ""),
            "Position": detail.get("position"),
            "Current Price": detail.get("current_price"),
            "Average Buy Price": detail.get("trade_price"),
            "Cost GBP": cost,
            "Market Value GBP": market_value,
            "Market Value %": market_value_pct,
            "Cumulative PnL GBP": detail.get("pnl"),
            "Cumulative Return %": standalone_return,
            "Daily Price Change LC": detail.get("price_change"),
            "Daily PnL GBP": detail.get("daily_pnl"),
            "Daily PnL bps": detail.get("bps_change"),
            "PnL Contribution bps": ((detail.get("daily_pnl") or 0) / abs(total_market_value) * 10000) if total_market_value else 0,
            "Daily FX PnL GBP": detail.get("fx_pnl"),
            "Daily FX PnL bps": ((detail.get("fx_pnl") or 0) / abs(total_market_value) * 10000) if total_market_value else 0,
            "Cumulative FX PnL GBP": detail.get("cumulative_fx_pnl"),
            "Cumulative FX Return %": (detail.get("cumulative_fx_return") or 0) / 100,
            "Holding Days": detail.get("initial_holding_days"),
            "Cumulative Dividend GBP": detail.get("cumulative dividend"),
            "Asset Type": detail.get("asset_type"),
            "Region": detail.get("region"),
            "Strategy": detail.get("Strategy"),
        })

    holdings_df = pd.DataFrame(rows)
    if not holdings_df.empty:
        holdings_df = holdings_df.sort_values("Cumulative Return %", ascending=False)
    return holdings_df


def build_strategy_holdings_table(analysis_result: object) -> pd.DataFrame:
    daily_pnl_result = analysis_result.get("daily_pnl_result") or {}
    market_details = daily_pnl_result.get("market_details") or []
    total_market_value = daily_pnl_result.get("total_market_value") or 0
    strategy_details = aggregate_holdings_by_strategy(market_details, total_market_value)

    return pd.DataFrame([
        {
            "Market": detail.get("Strategy"),
            "Position": detail.get("position"),
            "Cost GBP": detail.get("cost"),
            "Cumulative Return %": detail.get("standalone_bps"),
            "Cumulative PnL GBP": detail.get("pnl"),
            "Cumulative FX Return %": (detail.get("cumulative_fx_return") or 0) / 100,
            "Cumulative FX PnL GBP": detail.get("cumulative_fx_pnl"),
            "Market Value GBP": detail.get("market_value"),
            "Market Value %": detail.get("market_value_pct"),
            "Holding Days": detail.get("initial_holding_days"),
            "Cumulative Dividend GBP": detail.get("cumulative dividend"),
        }
        for detail in strategy_details
    ])


def display_holdings_tables(analysis_result: object) -> None:
    holdings_df = build_holdings_table(analysis_result)
    strategy_holdings_df = build_strategy_holdings_table(analysis_result)
    if holdings_df.empty:
        st.info("No structured holdings data is available.")
        return

    st.markdown("### 持仓情况")
    overview_columns = [
        "Market",
        "Position",
        "Current Price",
        "Average Buy Price",
        "Cost GBP",
        "Cumulative Return %",
        "Cumulative PnL GBP",
        "Cumulative FX Return %",
        "Cumulative FX PnL GBP",
        "Market Value GBP",
        "Market Value %",
        "Holding Days",
        "Cumulative Dividend GBP",
    ]
    strategy_columns = [
        column
        for column in overview_columns
        if column not in {"Current Price", "Average Buy Price"}
    ]
    daily_columns = [
        "Market",
        "Position",
        "Daily PnL bps",
        "Daily Price Change LC",
        "Daily PnL GBP",
        "PnL Contribution bps",
        "Daily FX PnL GBP",
        "Daily FX PnL bps",
    ]
    classification_columns = [
        "Market",
        "Ticker",
        "Asset Type",
        "Region",
        "Strategy",
    ]
    display_df = holdings_df.copy()
    percent_columns = {"Market Value %", "Cumulative Return %", "Cumulative FX Return %"}
    for column in percent_columns:
        if column in display_df.columns:
            display_df[column] = display_df[column] * 100
    overview_display_df = display_df[overview_columns].rename(columns={
        "Market": "当前市场",
        "Position": "当前持仓",
        "Current Price": "当前价格(LC)",
        "Average Buy Price": "平均买入价格(LC)",
        "Cost GBP": "成本(GBP)",
        "Cumulative Return %": "累计独立损益(%)",
        "Cumulative PnL GBP": "累计盈亏(GBP)",
        "Cumulative FX Return %": "累计外汇损益(%)",
        "Cumulative FX PnL GBP": "累计外汇损益(GBP)",
        "Market Value GBP": "当前市值(GBP)",
        "Market Value %": "市值占比(%)",
        "Holding Days": "持有天数",
        "Cumulative Dividend GBP": "累计分红",
    })
    overview_number_formats = {
        "当前持仓": "%,.0f",
        "当前价格(LC)": "%,.2f",
        "平均买入价格(LC)": "%,.2f",
        "成本(GBP)": "%,.2fGBP",
        "累计独立损益(%)": "%.2f%%",
        "累计盈亏(GBP)": "%,.2fGBP",
        "累计外汇损益(%)": "%.2f%%",
        "累计外汇损益(GBP)": "%,.2fGBP",
        "当前市值(GBP)": "%,.2fGBP",
        "市值占比(%)": "%.2f%%",
        "持有天数": "%,.0fdays",
        "累计分红": "%,.2fGBP",
    }
    for column in overview_number_formats:
        overview_display_df[column] = pd.to_numeric(
            overview_display_df[column], errors="coerce"
        )

    strategy_display_df = strategy_holdings_df.copy()
    for column in percent_columns:
        if column in strategy_display_df.columns:
            strategy_display_df[column] = strategy_display_df[column] * 100
    strategy_display_df = strategy_display_df[strategy_columns].rename(columns={
        "Market": "策略",
        "Position": "当前持仓",
        "Cost GBP": "成本(GBP)",
        "Cumulative Return %": "累计独立损益(%)",
        "Cumulative PnL GBP": "累计盈亏(GBP)",
        "Cumulative FX Return %": "累计外汇损益(%)",
        "Cumulative FX PnL GBP": "累计外汇损益(GBP)",
        "Market Value GBP": "当前市值(GBP)",
        "Market Value %": "市值占比(%)",
        "Holding Days": "持有天数",
        "Cumulative Dividend GBP": "累计分红",
    })
    strategy_number_formats = {
        column: number_format
        for column, number_format in overview_number_formats.items()
        if column not in {"当前价格(LC)", "平均买入价格(LC)"}
    }
    for column in strategy_number_formats:
        strategy_display_df[column] = pd.to_numeric(
            strategy_display_df[column], errors="coerce"
        )
    daily_display_df = display_df[daily_columns].rename(columns={
        "Market": "市场",
        "Position": "当前持仓",
        "Daily PnL bps": "当日盈亏(bps)",
        "Daily Price Change LC": "当日价格变动(LC)",
        "Daily PnL GBP": "当日盈亏金额(GBP)",
        "PnL Contribution bps": "盈亏占比(bps)",
        "Daily FX PnL GBP": "当日外汇盈亏金额(GBP)",
        "Daily FX PnL bps": "当日外汇盈亏占比(bps)",
    })
    daily_display_df = daily_display_df.sort_values("当日盈亏金额(GBP)", ascending=False, na_position="last")
    daily_number_formats = {
        "当前持仓": "%,.0f",
        "当日盈亏(bps)": "%,.2fbps",
        "当日价格变动(LC)": "%,.2f",
        "当日盈亏金额(GBP)": "%,.2fGBP",
        "盈亏占比(bps)": "%,.2fbps",
        "当日外汇盈亏金额(GBP)": "%,.2fGBP",
        "当日外汇盈亏占比(bps)": "%,.2fbps",
    }
    for column in daily_number_formats:
        daily_display_df[column] = pd.to_numeric(
            daily_display_df[column], errors="coerce"
        )

    classification_display_df = display_df[classification_columns].rename(columns={
        "Market": "当前市场",
        "Ticker": "Ticker",
        "Asset Type": "资产类型",
        "Region": "地区",
        "Strategy": "策略",
    })

    overview_tab, strategy_tab, daily_tab, classification_tab = st.tabs(
        ["持仓情况", "策略持仓情况", "盈亏分析", "分类"]
    )
    with overview_tab:
        st.dataframe(
            overview_display_df,
            use_container_width=True,
            hide_index=True,
            column_config=build_number_column_config(
                overview_display_df,
                number_formats=overview_number_formats,
            ),
        )
    with strategy_tab:
        st.dataframe(
            strategy_display_df,
            use_container_width=True,
            hide_index=True,
            column_config=build_number_column_config(
                strategy_display_df,
                number_formats=strategy_number_formats,
            ),
        )
    with daily_tab:
        st.dataframe(
            daily_display_df,
            use_container_width=True,
            hide_index=True,
            column_config=build_number_column_config(
                daily_display_df,
                number_formats=daily_number_formats,
            ),
        )
    with classification_tab:
        st.dataframe(
            classification_display_df,
            use_container_width=True,
            hide_index=True,
        )


def dict_to_pnl_summary_df(values: dict | None, total_market_value: float) -> pd.DataFrame:
    rows = []
    for name, pnl in (values or {}).items():
        rows.append({
            "Name": name,
            "PnL GBP": pnl,
            "PnL bps": (pnl / total_market_value * 10000) if total_market_value else 0,
        })
    summary_df = pd.DataFrame(rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values("PnL bps", ascending=False)
    return summary_df


def dict_to_market_value_summary_df(values: dict | None, total_market_value: float) -> pd.DataFrame:
    rows = []
    for name, market_value in (values or {}).items():
        rows.append({
            "Name": name,
            "Market Value GBP": market_value,
            "Market Value %": (market_value / total_market_value) if total_market_value else 0,
        })
    summary_df = pd.DataFrame(rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values("Market Value GBP", ascending=False)
    return summary_df


def display_dataframe(df: pd.DataFrame, percent_columns: set[str] | None = None) -> None:
    if df.empty:
        st.info("No data available.")
        return

    display_df = df.copy()
    percent_columns = percent_columns or set()
    for column in percent_columns:
        if column in display_df.columns:
            display_df[column] = display_df[column] * 100
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config=build_number_column_config(display_df, percent_columns),
    )


def format_plain_number(value: object) -> str:
    if value is None or value == "" or pd.isna(value):
        return ""
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def format_percent_number(value: object) -> str:
    if value is None or value == "":
        return ""
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return str(value)


def format_value_with_unit(value: object, unit: str) -> str:
    formatted_value = format_plain_number(value)
    return f"{formatted_value}{unit}" if formatted_value else ""


def format_integer_with_unit(value: object, unit: str) -> str:
    if value is None or value == "" or pd.isna(value):
        return ""
    try:
        return f"{float(value):,.0f}{unit}"
    except (TypeError, ValueError):
        return str(value)


def format_summary_value(value: object, unit: str = "") -> str:
    if unit == "%":
        return format_percent_number(value)
    if unit == "fx4":
        if value is None or value == "" or pd.isna(value):
            return ""
        try:
            return f"{float(value):.4f}"
        except (TypeError, ValueError):
            return str(value)
    if unit:
        return format_value_with_unit(value, unit)
    return format_plain_number(value)


def display_report_summaries(analysis_result: object) -> None:
    daily_pnl_result = analysis_result.get("daily_pnl_result") or {}
    total_market_value = daily_pnl_result.get("total_market_value") or 0
    market_details = daily_pnl_result.get("market_details") or []
    index_return_row = market_details[0] if market_details else {}

    asset_type_pct = analysis_result.get("asset_type_pct") or []
    if asset_type_pct:
        st.markdown("### 资产类型市值分布")
        asset_type_df = pd.DataFrame([
            {
                "Asset Type": row.get("asset_type"),
                "Market Value %": row.get("percentage"),
            }
            for row in asset_type_pct
        ])
        display_dataframe(asset_type_df, {"Market Value %"})

    currency_summary = analysis_result.get("currency_summary") or {}
    if currency_summary:
        st.markdown("### 货币市值分布")
        currency_df = pd.DataFrame([
            {"项目": "USD市值", "数值": currency_summary.get("total_market_value_usd"), "单位": "USD"},
            {"项目": "USD资产(GBP)", "数值": currency_summary.get("usd_gbp_value"), "单位": "GBP"},
            {"项目": "USD资产%", "数值": currency_summary.get("usd_percentage"), "单位": "%"},
            {"项目": "GBP市值", "数值": currency_summary.get("total_market_value_gbp"), "单位": "GBP"},
            {"项目": "GBP资产%", "数值": currency_summary.get("gbp_percentage"), "单位": "%"},
            {"项目": "总市值", "数值": currency_summary.get("total_market_value"), "单位": "GBP"},
            {"项目": "当日GBP/USD", "数值": currency_summary.get("gbpusd_fx"), "单位": "fx4"},
            {"项目": "当日GBP/USD move", "数值": currency_summary.get("gbpusd_move_bps"), "单位": "bps"},
        ])
        percent_mask = currency_df["单位"].eq("%")
        currency_df.loc[percent_mask, "数值"] = currency_df.loc[percent_mask, "数值"] * 100
        currency_df["数值"] = currency_df.apply(lambda row: format_summary_value(row["数值"], row["单位"]), axis=1)
        st.dataframe(currency_df[["项目", "数值"]], use_container_width=True, hide_index=True)

    portfolio_summary = analysis_result.get("portfolio_summary") or {}
    if portfolio_summary:
        st.markdown("### 组合汇总")
        totals_df = pd.DataFrame([
            {"项目": "总市值", "数值": portfolio_summary.get("total_market_value")},
            {"项目": "总成本", "数值": portfolio_summary.get("total_cost")},
            {"项目": "总盈亏(包括分红)", "数值": portfolio_summary.get("total_pnl")},
            {"项目": "历史已实现盈亏", "数值": portfolio_summary.get("realized_pnl")},
            {"项目": "总盈亏（包括未实现）", "数值": portfolio_summary.get("total_pnl_including_realized")},
        ])
        totals_df["数值"] = totals_df["数值"].map(lambda value: format_value_with_unit(value, "GBP"))
        st.dataframe(totals_df, use_container_width=True, hide_index=True)

    st.markdown("### 汇总信息")
    daily_summary_df = pd.DataFrame([
        {"项目": "日期", "数值": daily_pnl_result.get("date").strftime("%Y-%m-%d") if daily_pnl_result.get("date") is not None else "", "单位": ""},
        {"项目": "当日贡献度", "数值": (daily_pnl_result.get("total_daily_pnl") or 0) / total_market_value * 10000 if total_market_value else 0, "单位": "bps"},
        {"项目": "当日外汇贡献度", "数值": (daily_pnl_result.get("total_fx_pnl") or 0) / total_market_value * 10000 if total_market_value else 0, "单位": "bps"},
        {"项目": "当日非外汇贡献度", "数值": (daily_pnl_result.get("total_non_fx_pnl") or 0) / total_market_value * 10000 if total_market_value else 0, "单位": "bps"},
        {"项目": "当日S&P500贡献度", "数值": index_return_row.get("S&P 500 daily return") * 10000 if index_return_row.get("S&P 500 daily return") is not None else None, "单位": "bps"},
        {"项目": "当日NASDAQ贡献度", "数值": index_return_row.get("NASDAQ daily return") * 10000 if index_return_row.get("NASDAQ daily return") is not None else None, "单位": "bps"},
        {"项目": "当日总盈亏", "数值": daily_pnl_result.get("total_daily_pnl"), "单位": "GBP"},
        {"项目": "当日外汇盈亏", "数值": daily_pnl_result.get("total_fx_pnl"), "单位": "GBP"},
        {"项目": "当日非外汇盈亏", "数值": daily_pnl_result.get("total_non_fx_pnl"), "单位": "GBP"},
        {"项目": "当日总市值", "数值": total_market_value, "单位": "GBP"},
    ])
    daily_summary_df["数值"] = daily_summary_df.apply(lambda row: format_summary_value(row["数值"], row.get("单位", "")), axis=1)
    st.dataframe(daily_summary_df[["项目", "数值"]], use_container_width=True, hide_index=True)

    st.markdown("### Region PnL Summary")
    region_pnl_df = dict_to_pnl_summary_df(analysis_result.get("region_pnl"), total_market_value)
    if not region_pnl_df.empty:
        region_pnl_df["PnL GBP"] = region_pnl_df["PnL GBP"].map(lambda value: format_value_with_unit(value, "GBP"))
        region_pnl_df["PnL bps"] = region_pnl_df["PnL bps"].map(lambda value: format_value_with_unit(value, "bps"))
    st.dataframe(region_pnl_df, use_container_width=True, hide_index=True)

    st.markdown("### Strategy PnL Summary")
    strategy_pnl_df = dict_to_pnl_summary_df(analysis_result.get("strategy_pnl"), total_market_value)
    if not strategy_pnl_df.empty:
        strategy_pnl_df = strategy_pnl_df.sort_values("PnL GBP", ascending=False)
        strategy_pnl_df["PnL GBP"] = strategy_pnl_df["PnL GBP"].map(lambda value: format_value_with_unit(value, "GBP"))
        strategy_pnl_df["PnL bps"] = strategy_pnl_df["PnL bps"].map(lambda value: format_value_with_unit(value, "bps"))
    st.dataframe(strategy_pnl_df, use_container_width=True, hide_index=True)

    st.markdown("### Region Market Value Summary")
    region_market_value_df = dict_to_market_value_summary_df(analysis_result.get("region_market_value"), total_market_value)
    if not region_market_value_df.empty:
        region_market_value_df["Market Value GBP"] = region_market_value_df["Market Value GBP"].map(lambda value: format_value_with_unit(value, "GBP"))
        region_market_value_df["Market Value %"] = (region_market_value_df["Market Value %"] * 100).map(format_percent_number)
    st.dataframe(region_market_value_df, use_container_width=True, hide_index=True)

    st.markdown("### Strategy Market Value Summary")
    strategy_market_value_df = dict_to_market_value_summary_df(analysis_result.get("strategy_market_value"), total_market_value)
    if not strategy_market_value_df.empty:
        strategy_market_value_df["Market Value GBP"] = strategy_market_value_df["Market Value GBP"].map(lambda value: format_value_with_unit(value, "GBP"))
        strategy_market_value_df["Market Value %"] = (strategy_market_value_df["Market Value %"] * 100).map(format_percent_number)
    st.dataframe(strategy_market_value_df, use_container_width=True, hide_index=True)


def run_followup_step(
    step_name: str,
    target_date: object,
    data_source: str,
    lookback_period: int,
    cumulative_start_date: object,
    cumulative_end_date: object,
    drawdown_securities: list[str] | None = None,
) -> tuple[int, str, list[bytes], list[dict[str, object]]]:
    buffer = StringIO()
    images: list[bytes] = []
    cumulative_charts: list[dict[str, object]] = []
    cumulative_result: dict[str, object] | None = None
    try:
        import matplotlib.pyplot as plt

        from utils.analyzer import (
            analyze_portfolio_industry_percentiles,
            calculate_cumulative_contribution,
            display_index_top_constituents_performance,
            display_upcoming_dividends,
            portfolio_drawdown_monitor,
        )

        target_date_str = target_date.strftime("%Y-%m-%d")
        with redirect_stdout(buffer), redirect_stderr(buffer):
            if step_name == "prompt_for_constituents":
                display_index_top_constituents_performance(top_n=10)
            elif step_name == "run_portfolio_drawdown_monitor":
                portfolio_drawdown_monitor(
                    running_date=target_date_str,
                    lookback_period=lookback_period,
                    data_source=data_source,
                    selected_security=drawdown_securities,
                )
            elif step_name == "run_dividend_display":
                display_upcoming_dividends(
                    running_date=target_date_str,
                    data_source=data_source,
                )
            elif step_name == "analyze_portfolio_industry_percentiles":
                analyze_portfolio_industry_percentiles(
                    target_date=target_date_str,
                    data_source=data_source,
                )
            elif step_name == "calculate_cumulative_contribution":
                cumulative_result = calculate_cumulative_contribution(
                    cumulative_start_date.strftime("%Y-%m-%d"),
                    cumulative_end_date.strftime("%Y-%m-%d"),
                    data_source=data_source,
                    print_daily_table=False,
                )
            else:
                raise ValueError(f"Unknown follow-up step: {step_name}")

        for figure_number in plt.get_fignums():
            figure = plt.figure(figure_number)
            if step_name == "calculate_cumulative_contribution":
                chart_data = build_cumulative_return_chart_data(figure)
                if chart_data is not None:
                    cumulative_charts.append(chart_data)
                continue
            image_buffer = BytesIO()
            figure.savefig(image_buffer, format="png", bbox_inches="tight")
            image_buffer.seek(0)
            images.append(image_buffer.getvalue())
        if step_name == "calculate_cumulative_contribution" and cumulative_result:
            daily_contribution_rows = cumulative_result.get(
                "daily_contribution_rows",
                [],
            )
            if daily_contribution_rows:
                cumulative_charts.insert(
                    0,
                    {
                        "chart_type": "daily_contribution_table",
                        "title": (
                            f"{cumulative_start_date:%Y-%m-%d}至"
                            f"{cumulative_end_date:%Y-%m-%d}的盈亏分析"
                        ),
                        "records": daily_contribution_rows,
                    },
                )
            percentile_records = cumulative_result.get("percentile_comparison", [])
            if percentile_records:
                cumulative_charts.append(
                    {
                        "chart_type": "percentile_comparison",
                        "records": percentile_records,
                    }
                )
        plt.close("all")
        return 0, buffer.getvalue(), images, cumulative_charts
    except Exception as exc:
        print(f"Streamlit follow-up error: {exc}", file=buffer)
        return 1, buffer.getvalue(), images, cumulative_charts
