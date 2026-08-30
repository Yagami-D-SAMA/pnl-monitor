from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from .annual_return_analysis import (
    DEFAULT_INDEX_NAMES,
    INDEX_TICKERS,
    AnnualReturnAnalysis,
    DailyPnlAudit,
    audit_daily_pnl_dates,
    run_annual_return_analysis,
)
from .streamlit_portfolio_helpers import display_cumulative_return_chart


CLASSIFICATION_LABELS = {
    "missing_both_markets_open": "缺失：NYSE与LSE均开市",
    "missing_nyse_open_lse_holiday": "缺失：NYSE开市、LSE休市",
    "nyse_holiday_lse_open": "跨市场缺口：NYSE休市、LSE开市",
    "both_markets_closed": "非缺失：NYSE与LSE均休市",
}

STATUS_LABELS = {
    "Complete": "完整",
    "Incomplete trading dates": "完整日历年，但缺交易日",
    "Partial calendar year": "非完整日历年",
}

METRIC_LABELS = {
    "annual_return_pct": "累计收益率 (%)",
    "annualized_volatility_pct": "年化波动率 (%)",
    "max_drawdown_pct": "最大回撤 (%)",
    "sharpe_ratio": "Sharpe Ratio",
}


def _year_list(years: tuple[int, ...]) -> str:
    return ", ".join(str(year) for year in years) if years else "无"


def _display_date_audit(audit: DailyPnlAudit) -> None:
    if audit.missing_dates.empty:
        true_missing = audit.missing_dates
        nyse_holiday_lse_open = audit.missing_dates
        both_closed = audit.missing_dates
    else:
        true_missing = audit.missing_dates[audit.missing_dates["is_true_missing"]]
        nyse_holiday_lse_open = audit.missing_dates[
            audit.missing_dates["classification"] == "nyse_holiday_lse_open"
        ]
        both_closed = audit.missing_dates[
            audit.missing_dates["classification"] == "both_markets_closed"
        ]

    summary_cols = st.columns(4)
    summary_cols[0].metric("Daily PnL files", f"{len(audit.file_paths):,}")
    summary_cols[1].metric(
        "Coverage",
        f"{audit.start_date:%Y-%m-%d} to {audit.end_date:%Y-%m-%d}",
    )
    summary_cols[2].metric("完整日历年份", _year_list(audit.full_calendar_years))
    summary_cols[3].metric(
        "完整NYSE交易年份",
        _year_list(audit.complete_trading_years),
    )
    st.caption(
        "NYSE+LSE 交易日并集无缺口年份："
        + _year_list(audit.complete_union_years)
    )

    st.caption(
        "完整性以现有文件规律对应的 NYSE 交易日为主标准，同时交叉检查 LSE。"
        "周末和交易所休市日不会被当作真实缺失。"
    )
    year_display = audit.year_summary.copy()
    year_display["status"] = year_display["status"].map(STATUS_LABELS)
    year_display = year_display.rename(
        columns={
            "year": "年份",
            "coverage_start": "首个文件日期",
            "coverage_end": "最后文件日期",
            "file_count": "文件数",
            "expected_nyse_sessions": "NYSE应有交易日",
            "missing_nyse_sessions": "缺失NYSE交易日数",
            "missing_nyse_dates": "缺失NYSE日期",
            "missing_union_sessions": "NYSE+LSE并集缺失数",
            "missing_union_dates": "NYSE+LSE并集缺失日期",
            "us_holiday_uk_open_without_file": "美国休市/英国开市无文件",
            "extra_non_nyse_files": "非NYSE交易日文件数",
            "status": "状态",
        }
    )
    year_display = year_display[
        [
            "年份",
            "首个文件日期",
            "最后文件日期",
            "文件数",
            "NYSE应有交易日",
            "缺失NYSE交易日数",
            "缺失NYSE日期",
            "NYSE+LSE并集缺失数",
            "NYSE+LSE并集缺失日期",
            "美国休市/英国开市无文件",
            "非NYSE交易日文件数",
            "状态",
        ]
    ]
    st.dataframe(year_display, use_container_width=True, hide_index=True)

    qa_cols = st.columns(4)
    qa_cols[0].metric("真实缺失交易日", f"{len(true_missing):,}")
    qa_cols[1].metric(
        "美国休市/英国开市缺口",
        f"{len(nyse_holiday_lse_open):,}",
    )
    qa_cols[2].metric("两市场共同休市", f"{len(both_closed):,}")
    qa_cols[3].metric("排除的周末日期", f"{audit.weekend_dates_without_files:,}")

    if audit.weekend_files:
        st.warning(
            "存在周末文件：" + ", ".join(audit.weekend_files)
        )
    if audit.both_markets_closed_files:
        st.info(
            "NYSE 与 LSE 均休市但目录中仍存在文件："
            + ", ".join(audit.both_markets_closed_files)
            + "。仅作提示，文件未被修改。"
        )
    if true_missing.empty:
        st.success("在覆盖区间内未发现 NYSE 开市但 Daily PnL 文件缺失的日期。")
    else:
        st.error(
            "NYSE主日历缺失日期："
            + ", ".join(
                pd.to_datetime(true_missing["date"]).dt.strftime("%Y-%m-%d")
            )
        )
    if not nyse_holiday_lse_open.empty:
        st.warning(
            "按 NYSE+LSE 交易日并集，另有跨市场缺口："
            + ", ".join(
                pd.to_datetime(nyse_holiday_lse_open["date"]).dt.strftime(
                    "%Y-%m-%d"
                )
            )
        )

    with st.expander("查看所有无文件工作日及休市分类", expanded=False):
        if audit.missing_dates.empty:
            st.success("没有无文件工作日。")
        else:
            missing_display = audit.missing_dates.copy()
            missing_display["date"] = pd.to_datetime(
                missing_display["date"]
            ).dt.strftime("%Y-%m-%d")
            missing_display["classification"] = missing_display[
                "classification"
            ].map(CLASSIFICATION_LABELS)
            missing_display = missing_display.rename(
                columns={
                    "date": "日期",
                    "weekday": "星期",
                    "classification": "分类",
                    "nyse_status": "NYSE",
                    "lse_status": "LSE",
                    "holiday_detail": "休市说明",
                }
            )
            st.dataframe(
                missing_display[
                    ["日期", "星期", "分类", "NYSE", "LSE", "休市说明"]
                ],
                use_container_width=True,
                hide_index=True,
            )


def _metric_matrix(
    metrics: pd.DataFrame,
    metric_name: str,
) -> pd.DataFrame:
    return (
        metrics.pivot_table(
            index="year",
            columns="asset",
            values=metric_name,
            aggfunc="last",
        )
        .sort_index()
        .rename_axis(index="Year", columns=None)
    )


def _display_portfolio_annual_summary(metrics: pd.DataFrame) -> None:
    portfolio_metrics = metrics.loc[
        metrics["asset"] == "Portfolio",
        [
            "year",
            "total_pnl_gbp",
            "annual_return_pct",
            "annualized_volatility_pct",
            "max_drawdown_pct",
            "risk_free_rate_pct",
            "sharpe_ratio",
            "observations",
            "status",
        ],
    ].sort_values("year")
    if portfolio_metrics.empty:
        return

    summary = portfolio_metrics.rename(
        columns={
            "year": "Year",
            "total_pnl_gbp": "Total PnL (GBP)",
            "annual_return_pct": "Cumulative Return",
            "annualized_volatility_pct": "Annualized Volatility",
            "max_drawdown_pct": "Maximum Drawdown",
            "risk_free_rate_pct": "US 10Y Risk-Free Rate",
            "sharpe_ratio": "Sharpe Ratio",
            "observations": "Observations",
            "status": "Status",
        }
    )
    summary["Total PnL (GBP)"] = summary["Total PnL (GBP)"].map(
        lambda value: "" if pd.isna(value) else f"{value:,.2f} GBP"
    )
    for column in (
        "Cumulative Return",
        "Annualized Volatility",
        "Maximum Drawdown",
        "US 10Y Risk-Free Rate",
    ):
        summary[column] = summary[column].map(
            lambda value: "" if pd.isna(value) else f"{value:.2f}%"
        )
    summary["Sharpe Ratio"] = summary["Sharpe Ratio"].map(
        lambda value: "" if pd.isna(value) else f"{value:.2f}"
    )

    st.markdown("#### Portfolio annual summary")
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.caption(
        "Total PnL is the sum of daily portfolio PnL for each displayed year. "
        "The risk-free rate is the average daily ^TNX 10-year Treasury yield "
        "over that year's analysis period. Sharpe annualizes daily excess "
        "returns using 252 trading days."
    )


def _display_metric_comparisons(analysis: AnnualReturnAnalysis) -> None:
    metrics = analysis.metrics.copy()
    metric_name = st.selectbox(
        "Comparison metric",
        options=list(METRIC_LABELS),
        format_func=METRIC_LABELS.get,
        key="annual_return_metric",
    )
    metric_label = METRIC_LABELS[metric_name]
    matrix = _metric_matrix(metrics, metric_name)

    st.markdown(f"#### {metric_label} matrix")
    metric_format = "%.2f%%" if metric_name.endswith("_pct") else "%.2f"
    number_config = {
        column: st.column_config.NumberColumn(column, format=metric_format)
        for column in matrix.columns
    }
    st.dataframe(
        matrix,
        use_container_width=True,
        column_config=number_config,
    )

    heatmap_data = metrics[["year", "asset", metric_name]].dropna().copy()
    color_scale = (
        alt.Scale(scheme="viridis")
        if metric_name == "annualized_volatility_pct"
        else alt.Scale(scheme="redblue", domainMid=0)
    )
    heatmap = (
        alt.Chart(heatmap_data)
        .mark_rect()
        .encode(
            x=alt.X("year:O", title="Year"),
            y=alt.Y("asset:N", title=None, sort=list(matrix.columns)),
            color=alt.Color(
                f"{metric_name}:Q",
                title=metric_label,
                scale=color_scale,
            ),
            tooltip=[
                alt.Tooltip("year:O", title="Year"),
                alt.Tooltip("asset:N", title="Asset"),
                alt.Tooltip(f"{metric_name}:Q", title=metric_label, format=".2f"),
            ],
        )
        .properties(height=max(260, len(matrix.columns) * 28))
    )
    st.altair_chart(heatmap, use_container_width=True)

    comparison_cols = st.columns(2)
    available_years = sorted(int(year) for year in metrics["year"].unique())
    available_assets = list(dict.fromkeys(metrics["asset"].astype(str)))
    with comparison_cols[0]:
        horizontal_year = st.selectbox(
            "横向对比年份",
            available_years,
            index=len(available_years) - 1,
            key="annual_horizontal_year",
        )
        horizontal_data = metrics.loc[
            metrics["year"] == horizontal_year,
            ["asset", metric_name],
        ].dropna()
        horizontal_chart = (
            alt.Chart(horizontal_data)
            .mark_bar()
            .encode(
                x=alt.X("asset:N", title=None, sort="-y"),
                y=alt.Y(f"{metric_name}:Q", title=metric_label),
                color=alt.Color("asset:N", title=None, legend=None),
                tooltip=[
                    alt.Tooltip("asset:N", title="Asset"),
                    alt.Tooltip(
                        f"{metric_name}:Q",
                        title=metric_label,
                        format=".2f",
                    ),
                ],
            )
            .properties(title=f"{horizontal_year} asset comparison", height=360)
        )
        st.altair_chart(horizontal_chart, use_container_width=True)

    with comparison_cols[1]:
        vertical_asset = st.selectbox(
            "纵向对比资产",
            available_assets,
            key="annual_vertical_asset",
        )
        vertical_data = metrics.loc[
            metrics["asset"] == vertical_asset,
            ["year", metric_name],
        ].dropna()
        vertical_chart = (
            alt.Chart(vertical_data)
            .mark_bar(color="#1f77b4")
            .encode(
                x=alt.X("year:O", title="Year"),
                y=alt.Y(f"{metric_name}:Q", title=metric_label),
                tooltip=[
                    alt.Tooltip("year:O", title="Year"),
                    alt.Tooltip(
                        f"{metric_name}:Q",
                        title=metric_label,
                        format=".2f",
                    ),
                ],
            )
            .properties(title=f"{vertical_asset} year comparison", height=360)
        )
        st.altair_chart(vertical_chart, use_container_width=True)


def _display_year_over_year_changes(metrics: pd.DataFrame) -> None:
    return_matrix = _metric_matrix(metrics, "annual_return_pct")
    if len(return_matrix.index) < 2:
        return
    changes = return_matrix.diff().iloc[1:].copy()
    years = list(return_matrix.index)
    changes.index = [
        f"{int(previous) % 100:02d}-{int(current) % 100:02d}"
        for previous, current in zip(years[:-1], years[1:], strict=True)
    ]
    changes.index.name = "Year comparison"
    st.markdown("#### Year-on-year return change (percentage points)")
    st.dataframe(changes.style.format("{:.2f}"), use_container_width=True)


def _display_cumulative_paths(analysis: AnnualReturnAnalysis) -> None:
    paths = analysis.cumulative_paths.copy()
    if paths.empty:
        st.info("No cumulative return paths are available.")
        return

    st.markdown("#### Cumulative return paths")
    available_years = sorted(int(year) for year in paths["year"].unique())
    selected_year = st.selectbox(
        "同年横向路径对比",
        available_years,
        index=len(available_years) - 1,
        key="annual_path_year",
    )
    selected_paths = paths[paths["year"] == selected_year]
    chart_records = [
        {
            "date": row.date.isoformat(),
            "series": row.asset,
            "cumulative_return": float(row.cumulative_return),
        }
        for row in selected_paths.itertuples(index=False)
    ]
    display_cumulative_return_chart(
        {
            "title": f"{selected_year} Portfolio and Index Cumulative Return",
            "y_axis_title": "Cumulative Return (Base = 1)",
            "value_format": ".4f",
            "records": chart_records,
        }
    )

    available_assets = list(dict.fromkeys(paths["asset"].astype(str)))
    selected_asset = st.selectbox(
        "同一资产跨年路径对比",
        available_assets,
        key="annual_path_asset",
    )
    asset_paths = paths[paths["asset"] == selected_asset].copy()
    asset_paths["year_label"] = asset_paths["year"].astype(str)
    selected_line = alt.selection_point(fields=["year_label"], bind="legend")
    cross_year_chart = (
        alt.Chart(asset_paths)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X(
                "comparison_date:T",
                title="Calendar month",
                axis=alt.Axis(format="%b", tickCount="month", labelAngle=0),
            ),
            y=alt.Y(
                "cumulative_return:Q",
                title="Cumulative Return (Base = 1)",
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color("year_label:N", title="Year"),
            opacity=alt.condition(selected_line, alt.value(1.0), alt.value(0.18)),
            strokeWidth=alt.condition(selected_line, alt.value(4.0), alt.value(1.5)),
            tooltip=[
                alt.Tooltip("year_label:N", title="Year"),
                alt.Tooltip("date:T", title="Date", format="%Y-%m-%d"),
                alt.Tooltip(
                    "cumulative_return:Q",
                    title="Cumulative Return",
                    format=".4f",
                ),
            ],
        )
        .add_params(selected_line)
        .properties(title=f"{selected_asset} cumulative paths by year", height=450)
    )
    st.altair_chart(cross_year_chart, use_container_width=True)


def _display_analysis_result(analysis: AnnualReturnAnalysis) -> None:
    for warning in analysis.warnings:
        st.warning(warning)
    if analysis.metrics.empty:
        st.warning("No annual metrics were generated.")
        return

    _display_portfolio_annual_summary(analysis.metrics)
    _display_metric_comparisons(analysis)
    _display_year_over_year_changes(analysis.metrics)
    _display_cumulative_paths(analysis)


def display_historical_annual_return_analysis(
    pnl_dir: Path,
    data_source: str,
) -> None:
    """Render the additive, read-only annual-return workflow."""
    st.markdown("### 往年累计收益分析")
    show_analysis = st.toggle(
        "Display historical annual return analysis",
        value=False,
        key="show_historical_annual_return_analysis",
    )
    if not show_analysis:
        return

    try:
        audit = audit_daily_pnl_dates(pnl_dir, data_source=data_source)
    except (FileNotFoundError, ValueError) as exc:
        st.warning(str(exc))
        return

    _display_date_audit(audit)
    available_years = [int(year) for year in audit.year_summary["year"]]
    default_years = list(audit.full_calendar_years) or available_years
    selected_years = st.multiselect(
        "Analysis years",
        options=available_years,
        default=default_years,
        help="Defaults to calendar years covered from January through December.",
        key="historical_annual_years",
    )
    selected_indices = st.multiselect(
        "Benchmark indices",
        options=list(INDEX_TICKERS),
        default=list(DEFAULT_INDEX_NAMES),
        key="historical_annual_indices",
    )
    configuration = (
        data_source,
        tuple(sorted(selected_years)),
        tuple(selected_indices),
    )

    if st.button(
        "Run historical annual return analysis",
        type="primary",
        use_container_width=True,
        key="run_historical_annual_return_analysis",
        disabled=not bool(selected_years),
    ):
        with st.spinner("Reading Daily PnL and downloading selected indices..."):
            try:
                analysis = run_annual_return_analysis(
                    audit,
                    years=selected_years,
                    index_names=selected_indices,
                )
            except (OSError, ValueError) as exc:
                st.error(f"Historical annual analysis failed: {exc}")
            else:
                st.session_state.historical_annual_analysis = analysis
                st.session_state.historical_annual_configuration = configuration

    saved_analysis = st.session_state.get("historical_annual_analysis")
    saved_configuration = st.session_state.get("historical_annual_configuration")
    if saved_analysis is not None and saved_configuration == configuration:
        _display_analysis_result(saved_analysis)
    elif saved_analysis is not None:
        st.info("Selections changed. Run the analysis again to refresh the comparison.")
