"""
投资组合分析主程序
用于分析投资组合的盈亏情况、计算累计贡献度等
"""

from utils.analyzer import (
    analyze_portfolio,
    load_historical_pnl,
    calculate_cumulative_contribution,
    run_historical_analysis
)

if __name__ == "__main__":
    # 用法示例：
    # 1. 计算今日PnL
    analyze_portfolio(data_source='ALL')
    # 2. 查看历史PnL
    # load_historical_pnl('2025-04-02', data_source='ALL')
    # 3. 计算累计贡献度
    # calculate_cumulative_contribution('2024-01-01', '2025-04-12', data_source='ALL')
    # 4. 运行历史分析
    # run_historical_analysis('2025-01-01', '2024-04-11')

# TODO Compare against SP500 with chart, fix SP500 date issue
# TODO Compare against SP500 in cumulative return series
# TODO Calculate alpha over SP500 and major indices
# TODO Calculate hit ratio and portfolio stats
# TODO Display historical pnl
# TODO Dividend Calculation