import yfinance as yf
import pandas as pd
import os

def calculate_positions(trades_df):
    """计算当前持仓"""
    markets = trades_df['Market'].unique()
    current_positions = {}

    for market in markets:
        market_trades = trades_df[trades_df['Market'] == market].sort_values(['TextDate', 'Time'])
        position = 0
        buy_trades = []
        initial_fx_rate = None
        initial_settlement_date = None

        for _, trade in market_trades.iterrows():
            if trade['Direction'] == 'BUY':
                if trade['Activity'] == 'CORPORATE ACTION':
                    for buy_trade in buy_trades:
                        buy_trade['quantity'] = trade['Quantity']
                        buy_trade['remaining_quantity'] = trade['Quantity']
                    position += trade['Quantity']
                else:
                    # 记录第一次买入时的汇率和settlement date
                    if initial_fx_rate is None and 'Conversion rate' in trade:
                        initial_fx_rate = trade['Conversion rate']
                    if initial_settlement_date is None and 'Settlement date' in trade:
                        initial_settlement_date = pd.to_datetime(trade['Settlement date'], format='%d/%m/%Y')
                    buy_trades.append({
                        'quantity': trade['Quantity'],
                        'cost': trade['Cost/Proceeds'],
                        'remaining_quantity': trade['Quantity'],
                        'consideration': trade['Consideration']
                    })
                    position += trade['Quantity']
            else:  # SELL
                sell_quantity = -trade['Quantity']
                remaining_sell = sell_quantity

                for buy_trade in buy_trades:
                    if buy_trade['remaining_quantity'] > 0 and remaining_sell > 0:
                        matched_quantity = min(buy_trade['remaining_quantity'], remaining_sell)
                        buy_trade['remaining_quantity'] -= matched_quantity
                        remaining_sell -= matched_quantity
                        position -= matched_quantity

        cost = sum(-buy_trade['cost'] * (buy_trade['remaining_quantity'] / buy_trade['quantity'])
                   for buy_trade in buy_trades
                   if buy_trade['remaining_quantity'] > 0)
        consideration = sum(-buy_trade['consideration'] * (buy_trade['remaining_quantity'] / buy_trade['quantity'])
                            for buy_trade in buy_trades
                            if buy_trade['remaining_quantity'] > 0)

        if position != 0:
            current_positions[market] = {
                'position': position,
                'cost': cost,
                'ccy': trades_df[trades_df['Market'] == market]['Currency'].iloc[0],
                'initial_fx_rate': initial_fx_rate,
                'initial_settlement_date': initial_settlement_date,
                'last_buy_date': market_trades[market_trades['Direction'] == 'BUY'].iloc[-1]['TextDate'] if len(
                    market_trades[market_trades['Direction'] == 'BUY']) > 0 else None,
                'trade_price': trades_df[trades_df['Market'] == market]['Price'].iloc[0],
                'consideration': consideration
            }
    return current_positions


def calculate_market_values(current_positions, market_ticker_map, target_date, GBPUSD_FX, GBPUSD_FX_prev):
    """计算市场价值和盈亏"""
    daily_pnl_data = []
    total_market_value = 0
    total_pnl = 0
    total_cost = 0

    for market, position in current_positions.items():
        if market in market_ticker_map:
            ticker = market_ticker_map[market]
            try:
                stock = yf.Ticker(ticker)
                hist_data = stock.history(start=(target_date - pd.Timedelta(days=5)), end=target_date)

                if len(hist_data.index) >= 2:
                    latest_date = hist_data.index[-1]
                    prev_day = hist_data.index[-2]
                    current_price = float(hist_data.loc[latest_date, 'Close'])
                    prev_price = float(hist_data.loc[prev_day, 'Close'])

                    # 检查是否有分红
                    dividend = float(hist_data.loc[latest_date, 'Dividends']) if 'Dividends' in hist_data.columns else 0
                    if dividend > 0:
                        print(f"{market} 今日分红: {dividend:.4f}")

                    # 将分红计入价格变动
                    price_change = (current_price - prev_price + dividend)

                    # 计算持有时间
                    holding_days = None
                    if position['initial_settlement_date'] is not None:
                        holding_days = (latest_date.date() - position['initial_settlement_date'].date()).days
                    holding_days_latest = None
                    if position['last_buy_date'] is not None:
                        holding_days_latest = (latest_date.date() - position['last_buy_date'].date()).days

                    # 价格调整
                    if ticker == 'FLOS.L':
                        price_change = 0
                        current_price = 6.37
                    if position['ccy'] == 'GBP' and ticker not in {'INXG.L', 'IDTG.L', 'GOVP.L', 'ERNS.L'}:
                        current_price /= 100
                        prev_price /= 100
                        price_change /= 100
                        dividend /= 100

                    # 计算市值和盈亏
                    if position['ccy'] == 'USD':
                        market_value = current_price * position['position'] / GBPUSD_FX
                        non_fx_pnl = price_change * position['position'] / GBPUSD_FX
                        fx_change = (1 / GBPUSD_FX - 1 / GBPUSD_FX_prev)
                        fx_pnl = (current_price * position['position']) * fx_change
                        daily_pnl = non_fx_pnl + fx_pnl
                    else:
                        market_value = current_price * position['position']
                        daily_pnl = price_change * position['position']
                        fx_pnl = 0
                        non_fx_pnl = daily_pnl

                    pnl = market_value - position['cost']
                    # 计算bps时也要考虑分红的影响
                    bps_change = ((price_change) / prev_price) * 10000

                    # 计算累计外汇盈亏
                    cumulative_fx_return = 0
                    cumulative_fx_pnl = 0
                    if position['ccy'] != 'GBP' and position['initial_fx_rate'] is not None:
                        cumulative_fx_return = ((1 / position['initial_fx_rate']) / GBPUSD_FX - 1) * 100
                        if position['ccy'] == 'USD':
                            cumulative_fx_pnl = (position['consideration'] - current_price * position[
                                'position']) / GBPUSD_FX - (position['cost'] - market_value)

                    # 更新总计
                    total_market_value += market_value
                    total_pnl += pnl
                    total_cost += position['cost']

                    daily_pnl_data.append({
                        'market': market,
                        'price_change': price_change,
                        'daily_pnl': daily_pnl,
                        'fx_pnl': fx_pnl,
                        'non_fx_pnl': non_fx_pnl,
                        'bps_change': bps_change,
                        'market_value': market_value,
                        'position': position['position'],
                        'current_price': current_price,
                        'pnl': pnl,
                        'cost': position['cost'],
                        'cumulative_fx_return': cumulative_fx_return,
                        'cumulative_fx_pnl': cumulative_fx_pnl,
                        'initial_holding_days': holding_days_latest,
                        'last_buy_date': position['last_buy_date'],
                        'dividend': dividend,
                        'trade_price': position['trade_price']
                    })
            except Exception as e:
                print(f"获取{ticker}数据时发生错误: {e}")

    return daily_pnl_data, total_market_value, total_pnl, total_cost, latest_date


def calculate_realized_pnl(trades_df, markets):
    """计算已实现盈亏"""
    realized_pnl = 0
    for market in markets:
        market_trades = trades_df[trades_df['Market'] == market]
        closed_positions = market_trades[market_trades['Direction'] == 'SELL']
        if any(closed_positions['Activity'] == 'CORPORATE ACTION'):
            print(f"{market}市场存在Corporate actions，跳过pnl计算")
            continue

        if not closed_positions.empty:
            trade_pnl = 0
            buy_trades = market_trades[
                (market_trades['TextDate'] <= closed_positions['TextDate'].max()) &
                (market_trades['Direction'] == 'BUY')
                ].sort_values('TextDate')

            if buy_trades.empty:
                continue

            remaining_quantity = -closed_positions['Quantity'].sum()
            for _, buy_trade in buy_trades.iterrows():
                if remaining_quantity <= 0:
                    break
                matched_quantity = min(buy_trade['Quantity'], remaining_quantity)
                remaining_quantity -= matched_quantity

            if (closed_positions.shape[0] == 1) & (buy_trades.shape[0] == 1):
                trade_pnl += float(closed_positions['Cost/Proceeds'].iloc[0]) + float(
                    buy_trades['Cost/Proceeds'].iloc[0])
            elif (closed_positions.shape[0] == 1) & (buy_trades.shape[0] != 1):
                trade_pnl += float(closed_positions['Cost/Proceeds'].iloc[0]) + float(buy_trades['Cost/Proceeds'].sum())
            elif (closed_positions.shape[0] != 1) & (buy_trades.shape[0] == 1):
                trade_pnl += float(closed_positions['Cost/Proceeds'].sum()) + float(buy_trades['Cost/Proceeds'].iloc[0])
            else:
                trade_pnl += float(closed_positions['Cost/Proceeds'].sum()) + float(buy_trades['Cost/Proceeds'].sum())

            if remaining_quantity > 0:
                print(f"警告：{market}市场的卖出数量大于之前的买入数量")
            realized_pnl += trade_pnl

    return realized_pnl


def calculate_global_indices_return(target_date):
    """计算全球主要指数的当日回报率"""
    indices = {
        "S&P 500": "^GSPC",
        "Dow Jones": "^DJI",
        "Nasdaq 100": "^NDX",
        "Russell 2000": "^RUT",
        "Euro Stoxx 50": "^STOXX50E",
        "DAX (Germany)": "^GDAXI",
        "FTSE 100 (UK)": "^FTSE",
        "Nikkei 225 (Japan)": "^N225",
        "Hang Seng Index (Hong Kong)": "^HSI",
        "SSE Composite (Shanghai)": "000001.SS",
        "Nifty 50 (India)": "^NSEI",
        "Bovespa (Brazil)": "^BVSP"
    }

    results = {}
    latest_dates = {}

    for index_name, ticker in indices.items():
        try:
            index = yf.Ticker(ticker)
            hist_data = index.history(start=(target_date - pd.Timedelta(days=5)), end=target_date)

            if len(hist_data.index) >= 2:
                latest_date = hist_data.index[-1]
                prev_day = hist_data.index[-2]
                current_price = float(hist_data.loc[latest_date, 'Close'])
                prev_price = float(hist_data.loc[prev_day, 'Close'])

                return_bps = ((current_price / prev_price) - 1) * 10000
                results[index_name] = return_bps
                latest_dates[index_name] = latest_date
            else:
                print(f"警告：无法获取足够的{index_name}指数数据")
                results[index_name] = None
                latest_dates[index_name] = None
        except Exception as e:
            print(f"获取{index_name}指数数据时发生错误: {e}")
            results[index_name] = None
            latest_dates[index_name] = None

    return results, latest_dates


if __name__ == "__main__":
    # 测试计算功能
    print("测试计算模块")

    # 设置测试路径
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    investment_dir = os.path.join(os.path.dirname(base_dir), 'investment')
    trade_history_path = os.path.join(investment_dir, 'TradeHistory-SXAFI-(01-03-2017)-(02-03-2025).csv')
    enum_path = os.path.join(investment_dir, 'enum.csv')

    # 加载测试数据
    from .data_loader import load_trade_data, get_market_ticker_map

    trades_df, enum_df = load_trade_data([trade_history_path], enum_path)

    if trades_df is not None and enum_df is not None:
        # 测试持仓计算
        positions = calculate_positions(trades_df)
        print("\n当前持仓:")
        print(positions)

        # 测试市场价值计算
        market_ticker_map = get_market_ticker_map(trades_df, enum_df)
        from datetime import datetime

        daily_pnl_data, total_mv, total_pnl, total_cost, latest_date = calculate_market_values(
            positions, market_ticker_map, datetime.today(), 1.27, 1.26)

        print(f"\n总市值: {total_mv:,.2f}")
        print(f"总盈亏: {total_pnl:,.2f}")

        # 测试已实现盈亏计算
        realized_pnl = calculate_realized_pnl(trades_df, trades_df['Market'].unique())
        print(f"已实现盈亏: {realized_pnl:,.2f}")

        # 测试全球指数回报率计算
        indices_returns, indices_dates = calculate_global_indices_return(datetime.today())
        print("\n全球主要指数回报率:")
        for index_name, return_bps in indices_returns.items():
            if return_bps is not None:
                print(f"{index_name}: {return_bps:.2f}bps ({indices_dates[index_name].strftime('%Y-%m-%d')})")