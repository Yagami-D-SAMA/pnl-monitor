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
    portfolio_drawdown_monitor
)

def run_portfolio_drawdown_monitor(running_date=None, lookback_period=90, data_source='ALL'):
    return portfolio_drawdown_monitor(
        running_date=running_date,
        lookback_period=lookback_period,
        data_source=data_source,
    )

if __name__ == "__main__":
    # 用法示例：
    # 1. 计算今日PnL
    # todo 股票均线监控
    # todo build a database for historical price movement
    # todo build value factor construction
    # todo ETF price comparison
    # todo display top 10 constituents perf of main stream indices every day
    # todo China US EU PMI/CPI/Macro data analysis
    # todo improve UI user to zoom in trade for detail
    # todo N/A, need to re calculate price
    analyze_portfolio(data_source='ALL', asset_type=True)
    # stock_monitor(90)
    # run_portfolio_drawdown_monitor(running_date=None, lookback_period=90, data_source='ALL')
    # export_industry_price_returns()
    # analyze_portfolio_industry_percentiles()
    # stock_value_factor()
    # 3. 查看历史PnL
    # load_historical_pnl('2026-06-29', data_source='ALL')
    # 4. 计算累计贡献度
    # calculate_cumulative_contribution('2025-12-31', '2026-06-26', data_source='ALL')
    # 5. 运行历史分析
    # run_historical_analysis('2026-03-09', '2026-03-13')
