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
    stock_value_factor
)

if __name__ == "__main__":
    # 用法示例：
    # 1. 计算今日PnL
    # todo 股票均线监控
    # todo build a database for historical price movement
    # todo build value factor construction
    # todo ETF price comparison
    # todo dash or streamlit for visualisation tool
    analyze_portfolio(data_source='ALL', asset_type=True)
    # stock_monitor(90)
    # stock_value_factor()
    # 3. 查看历史PnL
    # load_historical_pnl('2026-05-26', data_source='ALL')
    # 4. 计算累计贡献度
    # calculate_cumulative_contribution('2025-12-31', '2026-05-27', data_source='ALL')
    # 5. 运行历史分析
    # run_historical_analysis('2026-03-09', '2026-03-13')
