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
    analyze_portfolio(data_source='ALL', asset_type=True)
    # 2. 查看历史PnL
    # load_historical_pnl('2025-05-02', data_source='ALL')
    # 3. 计算累计贡献度
    # calculate_cumulative_contribution('2023-01-01', '2025-05-02', data_source='ALL')
    # 4. 运行历史分析
    # run_historical_analysis('2025-04-25')

# TODO Compare against SP500 with chart, fix SP500 date issue
# TODO Compare against SP500 in cumulative return series
# TODO Calculate alpha over SP500 and major indices
# TODO Display historical pnl, and hist vol?
# TODO add portfolio analysis, asset type contribution and country breakdown
