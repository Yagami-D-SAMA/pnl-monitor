from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd


def _as_float(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def aggregate_holdings_by_strategy(
    market_details: Iterable[dict],
    total_market_value: float,
) -> list[dict]:
    """Aggregate position-level holding metrics into strategy-level rows."""
    grouped: dict[str, dict] = {}

    for detail in market_details:
        strategy = detail.get("Strategy")
        if strategy is None or (isinstance(strategy, float) and math.isnan(strategy)):
            strategy = detail.get("market") or "Unclassified"
        strategy = str(strategy)

        row = grouped.setdefault(
            strategy,
            {
                "market": strategy,
                "Strategy": strategy,
                "position": 0.0,
                "current_price": "N/A",
                "trade_price": "N/A",
                "cost": 0.0,
                "pnl": 0.0,
                "cumulative_fx_pnl": 0.0,
                "market_value": 0.0,
                "cumulative dividend": 0.0,
                "_holding_days_weighted_sum": 0.0,
                "_holding_days_weight": 0.0,
            },
        )

        position = _as_float(detail.get("position"))
        cost = _as_float(detail.get("cost"))
        market_value = _as_float(detail.get("market_value"))
        holding_days = _as_float(detail.get("initial_holding_days"))
        holding_weight = abs(market_value) or abs(cost)

        row["position"] += position
        row["cost"] += cost
        row["pnl"] += _as_float(detail.get("pnl"))
        row["cumulative_fx_pnl"] += _as_float(detail.get("cumulative_fx_pnl"))
        row["market_value"] += market_value
        row["cumulative dividend"] += _as_float(detail.get("cumulative dividend"))
        if holding_weight:
            row["_holding_days_weighted_sum"] += holding_days * holding_weight
            row["_holding_days_weight"] += holding_weight

    total_market_value = _as_float(total_market_value)
    strategy_rows = []
    for row in grouped.values():
        cost = row["cost"]
        holding_weight = row.pop("_holding_days_weight")
        weighted_holding_days = row.pop("_holding_days_weighted_sum")
        row["standalone_bps"] = row["pnl"] / abs(cost) if cost else 0.0
        row["cumulative_fx_return"] = (
            row["cumulative_fx_pnl"] / abs(cost) * 100 if cost else 0.0
        )
        row["market_value_pct"] = (
            row["market_value"] / total_market_value if total_market_value else 0.0
        )
        row["initial_holding_days"] = (
            weighted_holding_days / holding_weight if holding_weight else 0.0
        )
        strategy_rows.append(row)

    return sorted(strategy_rows, key=lambda item: item["standalone_bps"], reverse=True)


def build_cumulative_strategy_return(
    daily_strategy_data: Iterable[dict],
    top_n: int = 5,
    excluded_strategies: Iterable[str] = (),
) -> pd.DataFrame:
    """Build Base=1 returns for the largest strategies on the latest date."""
    if top_n <= 0:
        raise ValueError("top_n must be greater than zero")

    records = pd.DataFrame(daily_strategy_data)
    required_columns = {"date", "Strategy", "daily_pnl", "market_value"}
    if records.empty or not required_columns.issubset(records.columns):
        return pd.DataFrame()

    records = records.loc[
        :, ["date", "Strategy", "daily_pnl", "market_value"]
    ].copy()
    records["date"] = pd.to_datetime(records["date"], errors="coerce")
    records["daily_pnl"] = pd.to_numeric(records["daily_pnl"], errors="coerce")
    records["market_value"] = pd.to_numeric(
        records["market_value"], errors="coerce"
    )
    records["Strategy"] = records["Strategy"].fillna("Unclassified").astype(str)
    records = records.dropna(subset=["date", "daily_pnl", "market_value"])
    excluded_names = {
        str(strategy).strip().casefold()
        for strategy in excluded_strategies
        if str(strategy).strip()
    }
    if excluded_names:
        strategy_names = records["Strategy"].str.strip().str.casefold()
        records = records[~strategy_names.isin(excluded_names)]
    if records.empty:
        return pd.DataFrame()

    latest_date = records["date"].max()
    latest_market_value = (
        records.loc[records["date"] == latest_date]
        .groupby("Strategy")["market_value"]
        .sum()
        .sort_values(ascending=False)
    )
    selected_strategies = latest_market_value.head(top_n).index.tolist()
    if not selected_strategies:
        return pd.DataFrame()

    records = records[records["Strategy"].isin(selected_strategies)]
    daily_pnl = (
        records.pivot_table(
            index="date",
            columns="Strategy",
            values="daily_pnl",
            aggfunc="sum",
        )
        .sort_index()
        .reindex(columns=selected_strategies)
        .fillna(0.0)
        .astype(float)
    )
    market_value = records.pivot_table(
        index="date",
        columns="Strategy",
        values="market_value",
        aggfunc="sum",
    ).reindex(index=daily_pnl.index, columns=selected_strategies)

    daily_return = daily_pnl.divide(
        market_value.where(market_value.ne(0))
    ).fillna(0.0)
    daily_return.iloc[0] = 0.0
    return (1.0 + daily_return).cumprod()
