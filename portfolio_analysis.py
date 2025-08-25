"""
投资组合分析主程序
用于分析投资组合的盈亏情况、计算累计贡献度等
"""

from utils.analyzer import (
    analyze_portfolio,
    load_historical_pnl,
    calculate_cumulative_contribution,
    run_historical_analysis,
    stock_monitor
)

if __name__ == "__main__":
    # 用法示例：
    # 1. 计算今日PnL
    # analyze_portfolio(data_source='ALL', asset_type=True)
    # 2. 股票均线监控
    # stock_monitor(10)
    # 3. 查看历史PnL
    load_historical_pnl('2025-07-03', data_source='ALL')
    # 4. 计算累计贡献度
    # calculate_cumulative_contribution('2024-12-30', '2025-08-25', data_source='ALL')
    # 5. 运行历史分析
    # run_historical_analysis('2022-06-30', '2023-01-01')

