"""
投资组合分析主程序
用于分析投资组合的盈亏情况、计算累计贡献度等
"""

from utils.analyzer import (
    analyze_portfolio,
    load_historical_pnl,
    calculate_cumulative_contribution,
    run_historical_analysis,
    stock_monitor,
    stock_value_factor,
    export_industry_price_returns,
    analyze_portfolio_industry_percentiles,
    portfolio_drawdown_monitor,
    display_upcoming_dividends
)

def run_portfolio_drawdown_monitor(running_date=None, lookback_period=90, data_source='ALL'):
    return portfolio_drawdown_monitor(
        running_date=running_date,
        lookback_period=lookback_period,
        data_source=data_source,
    )

def run_dividend_display(running_date=None, data_source='ALL'):
    return display_upcoming_dividends(
        running_date=running_date,
        data_source=data_source,
    )

def _ask_to_run(next_step_name: str) -> bool:
    answer = input(f"\n是否开始运行 {next_step_name}? (y/N，回车跳过并继续询问下一个任务): ").strip().lower()
    return answer in {"y", "yes", "是"}

def run_portfolio_daily_workflow(
    running_date=None,
    data_source='ALL',
    asset_type=True,
    lookback_period=90,
    cumulative_start_date='2025-12-31',
    cumulative_end_date='2026-07-09',
):
    analyze_portfolio(target_date=running_date, data_source=data_source, asset_type=asset_type)

    if _ask_to_run("run_portfolio_drawdown_monitor"):
        run_portfolio_drawdown_monitor(
            running_date=running_date,
            lookback_period=lookback_period,
            data_source=data_source,
        )

    if _ask_to_run("run_dividend_display"):
        run_dividend_display(
            running_date=running_date,
            data_source=data_source,
        )

    if _ask_to_run("analyze_portfolio_industry_percentiles"):
        analyze_portfolio_industry_percentiles(
            target_date=running_date,
            data_source=data_source,
        )

    if _ask_to_run("calculate_cumulative_contribution"):
        calculate_cumulative_contribution(
            cumulative_start_date,
            cumulative_end_date,
            data_source=data_source,
        )

if __name__ == "__main__":
    # 用法示例：
    # 1. 计算今日PnL
    # todo 股票均线监控
    # todo build a database for historical price movement
    # todo build value factor construction
    # todo ETF price comparison
    # todo China US EU PMI/CPI/Macro data analysis
    # todo N/A, need to re calculate price
    # todo  daily run
    run_portfolio_daily_workflow(data_source='ALL', asset_type=True)
    # stock_monitor(90)
    # run_portfolio_drawdown_monitor(running_date=None, lookback_period=90, data_source='ALL')
    # run_dividend_display(running_date=None, data_source='ALL')
    # export_industry_price_returns()
    # analyze_portfolio_industry_percentiles()
    # stock_value_factor()
    # 3. 查看历史PnL
    # load_historical_pnl('2026-07-14', data_source='ALL')
    # 4. 计算累计贡献度
    # calculate_cumulative_contribution('2026-01-01', '2026-07-14', data_source='ALL')
    # 5. 运行历史分析
    # run_historical_analysis('2022-11-01', '2022-12-29')
