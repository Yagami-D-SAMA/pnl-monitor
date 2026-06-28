def _print_pnl_summary(title: str, pnl_by_group: dict, total_market_value: float) -> None:
    if not pnl_by_group or not total_market_value:
        return

    # 先计算 bps，再按 bps 排序（高 → 低）
    rows = []
    for name, pnl in pnl_by_group.items():
        bps = (pnl / total_market_value) * 10000
        rows.append((name, pnl, bps))
    rows.sort(key=lambda x: x[2], reverse=True)

    # 不同标题用不同的 name 列宽
    name_width = 50 if "Strategy" in title else 15

    print(f"\n{title}:")
    print("-" * (name_width + 32))
    print(f"{'Name':<{name_width}}  {'PnL(GBP)':>14}  {'PnL(bps)':>12}")
    print("-" * (name_width + 32))

    for name, pnl, bps in rows:
        print(f"{name:<{name_width}}  {pnl:>14,.2f}  {bps:>12,.2f}")

    print("-" * (name_width + 32))

def _print_market_value_summary(title: str, mv_by_group: dict, total_market_value: float) -> None:
    if not mv_by_group or not total_market_value:
        return

    rows = []
    for name, mv in mv_by_group.items():
        pct = (mv / total_market_value) * 100
        rows.append((name, mv, pct))
    rows.sort(key=lambda x: x[1], reverse=True)

    name_width = 50 if "Strategy" in title else 15

    print(f"\n{title}:")
    print("-" * (name_width + 24))
    print(f"{'Name':<{name_width}}  {'Market Value(GBP)':>14} {'Market Value %':>16}")
    print("-" * (name_width + 24))

    for name, mv, pct in rows:
        print(f"{name:<{name_width}}  {mv:>14,.2f} {pct:>16,.2f}%")

    print("-" * (name_width + 24))

def generate_report(daily_pnl_data, total_market_value, total_pnl, total_cost, realized_pnl, latest_date, region_pnl=None, region_market_value=None,
                    strategy_pnl=None, strategy_market_value=None):
    """生成报告"""
    # 获取全球指数回报率
    # from . import calculate_global_indices_return
    # indices_returns, indices_dates = calculate_global_indices_return(latest_date)
    
    # 对持仓情况按市值从大到小排序
    for index in daily_pnl_data:
        index['standalone_bps'] = index['pnl'] / abs(index['cost']) if index['cost'] != 0 else 0

    sorted_holdings = sorted(daily_pnl_data, key=lambda x: x['standalone_bps'], reverse=True)
    
    print(f"\n持仓情况 ({latest_date.strftime('%Y-%m-%d')}):")
    print("-" * 320)
    print(f"{'当前市场':<50} {'当前持仓':>10} {'当前价格(LC)':>8} {'平均买入价格(LC)':>12} {'成本(GBP)':>10} {'累计独立损益(%)':>15} {'累计盈亏(GBP)':>15}"
          f"{'累计外汇损益(%)':>15} {'累计外汇损益(GBP)':>15} {'当前市值(GBP)':>15} {'市值占比(%)':>10} {'持有天数':>7} {'累计分红':>7}")
    print("-" * 320)
    
    for data in sorted_holdings:
        market_value_contribution = (data['market_value'] / total_market_value * 100) if total_market_value != 0 else 0
        standalone_bps = data['standalone_bps'] * 100
        cumulative_dividend_text = f"{data['cumulative dividend']:>9,.2f}GBP" if 'cumulative dividend' in data else ""
        print(f"{data['market']:<50} {data['position']:>12.0f} {data['current_price']:>10,.2f} {data['trade_price']:>15,.2f} {data['cost']:>15,.2f}GBP"
              f"{standalone_bps:>12,.2f}% {data['pnl']:>15,.2f}GBP {data['cumulative_fx_return']:>15,.2f}% {data['cumulative_fx_pnl']:>18,.2f}GBP"
              f"{data['market_value']:>15,.2f}GBP {market_value_contribution:>10,.2f}% {data['initial_holding_days']:>9} days {cumulative_dividend_text}")
    
    print("-" * 320)
    print(f"总市值: {total_market_value:>15,.2f}")
    print(f"总成本: {total_cost:>15,.2f}")
    print(f"总盈亏(包括分红): {total_pnl:>10,.2f}")
    print(f"\n历史已实现盈亏: {realized_pnl:.2f}")
    print(f"总盈亏（包括未实现）: {(total_pnl + realized_pnl):.2f}")
    
    # 打印每日盈亏分析
    print(f"\n盈亏分析 ({latest_date.strftime('%Y-%m-%d')}):")
    print("-" * 180)
    print(f"{'市场':<50} {'当前持仓':>10} {'当日盈亏(bps)':>15} {'当日价格变动(LC)':>15} {'当日盈亏金额(GBP)':>15} {'盈亏占比(bps)':>10} {'当日外汇盈亏金额(GBP)':>15}"
          f"{'当日外汇盈亏占比(bps)':>15}")
    print("-" * 180)
    
    total_daily_pnl = sum(data['daily_pnl'] for data in daily_pnl_data)
    
    # 计算盈亏占比并排序
    pnl_analysis = []
    for data in daily_pnl_data:
        pnl_contribution = (data['daily_pnl'] / abs(total_market_value) * 10000) if total_market_value != 0 else 0
        fx_pnl_contribution = (data['fx_pnl'] / abs(total_market_value) * 10000) if total_market_value != 0 else 0
        pnl_analysis.append({
            'market': data['market'],
            'position': data['position'],
            'price_change': data['price_change'],
            'daily_pnl': data['daily_pnl'],
            'daily_fx_pnl': data['fx_pnl'],
            'bps_change': data['bps_change'],
            'fx_pnl_contribution': fx_pnl_contribution,
            'pnl_contribution': pnl_contribution,
            'regional_pnl': region_pnl
        })
    
    # 按盈亏占比从大到小排序
    sorted_pnl = sorted(pnl_analysis, key=lambda x: x['pnl_contribution'], reverse=True)
    
    for data in sorted_pnl:
        print(f"{data['market']:<50} {data['position']:>12,.0f} {data['bps_change']:>15,.2f}bps {data['price_change']:>15,.4f}"
              f"{data['daily_pnl']:>15,.2f}GBP {data['pnl_contribution']:>10,.2f}bps {data['daily_fx_pnl']:>20,.2f}GBP {data['fx_pnl_contribution']:>15,.2f}bps")
    
    # 打印汇总信息
    print("\n汇总信息:")
    print("-" * 100)
    print(f"日期: {latest_date.strftime('%Y-%m-%d')}")
    print("-" * 100)
    portfolio_return = (total_daily_pnl / total_market_value) * 10000 if total_market_value != 0 else 0
    print(f"{'当日贡献度:':<10} {portfolio_return:.2f}bps")
    print(f"{'当日外汇贡献度:':<8} {sum(data['fx_pnl'] for data in daily_pnl_data) / total_market_value * 10000:.2f}bps")
    print(f"{'当日非外汇贡献度:':<10} {sum(data['non_fx_pnl'] for data in daily_pnl_data) / total_market_value * 10000:.2f}bps")
    sp500_ret = daily_pnl_data[0].get('S&P 500 daily return') if daily_pnl_data else None
    if sp500_ret is not None:
        print(f"{'当日S&P500贡献度:':<10} {sp500_ret * 10000:.2f}bps")
    nasdaq_ret = daily_pnl_data[0].get('NASDAQ daily return') if daily_pnl_data else None
    if nasdaq_ret is not None:
        print(f"{'当日NASDAQ贡献度:':<10} {nasdaq_ret * 10000:.2f}bps")
    print(f"{'当日总盈亏:':<10} {total_daily_pnl:.2f}GBP")
    print(f"{'当日外汇盈亏:':<8} {sum(data['fx_pnl'] for data in daily_pnl_data):.2f}GBP")
    print(f"{'当日非外汇盈亏:':<6} {sum(data['non_fx_pnl'] for data in daily_pnl_data):.2f}GBP")
    print(f"{'当日总市值:':<10} {total_market_value:,.2f}GBP")

    # 在 generate_report 里：
    _print_pnl_summary("Region PnL Summary", region_pnl, total_market_value)
    _print_pnl_summary("Strategy PnL Summary", strategy_pnl, total_market_value)

    _print_market_value_summary("Region Market Value Summary", region_market_value, total_market_value)
    _print_market_value_summary("Strategy Market Value Summary", strategy_market_value, total_market_value)
    
    # 添加全球指数对比信息
    # print("\n全球主要指数对比分析:")
    # print("-" * 100)
    # print(f"{'指数名称':<30} {'回报率(bps)':>15} {'日期':>12} {'状态':>10}")
    # print("-" * 100)
    
    # for index_name, return_bps in indices_returns.items():
    #     if return_bps is not None:
    #         index_date = indices_dates[index_name]
    #         date_status = ""
    #         if index_date.date() != latest_date.date():
    #             date_status = "滞后"
    #         print(f"{index_name:<30} {return_bps:>15,.2f} {index_date.strftime('%Y-%m-%d'):>12} {date_status:>10}")
    #
    #         # 计算相对于该指数的超额收益
    #         if index_name == "S&P 500":  # 使用标普500作为主要对比基准
    #             excess_return = portfolio_return - return_bps
    #             print(f"{'相对{index_name}超额收益:':>30} {excess_return:>15,.2f}")
    # print("-" * 100)
    
    result =  {
        'date': latest_date,
        'total_daily_pnl': total_daily_pnl,
        'total_market_value': total_market_value,
        'total_fx_pnl': sum(data['fx_pnl'] for data in daily_pnl_data),
        'total_non_fx_pnl': sum(data['non_fx_pnl'] for data in daily_pnl_data),
        'market_details': daily_pnl_data,
        'realized_pnl': realized_pnl,
        'regional_pnl': region_pnl
    }
    if region_pnl is not None:
        result['regional_pnl'] = region_pnl
    return result

if __name__ == "__main__":
    # 测试报告生成功能
    print("测试报告生成模块")
    
    # 创建测试数据
    from datetime import datetime
    test_data = [
        {
            'market': 'AAPL',
            'position': 100,
            'cost': 15000,
            'market_value': 17000,
            'pnl': 2000,
            'daily_pnl': 500,
            'fx_pnl': 100,
            'non_fx_pnl': 400
        },
        {
            'market': 'MSFT',
            'position': 50,
            'cost': 12000,
            'market_value': 13000,
            'pnl': 1000,
            'daily_pnl': 300,
            'fx_pnl': 50,
            'non_fx_pnl': 250
        }
    ]
    
    # 生成测试报告
    total_mv = 30000
    total_pnl = 3000
    total_cost = 27000
    realized_pnl = 1000
    latest_date = datetime.today()
    
    generate_report(test_data, total_mv, total_pnl, total_cost, realized_pnl, latest_date) 
