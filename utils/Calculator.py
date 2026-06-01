import pandas as pd
import os
from datetime import datetime
import yfinance as yf
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import json
import time
from urllib.parse import urlencode
from urllib.request import urlopen

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "OLX51ZCO9GZDLBS2")
AV_BASE_URL = "https://www.alphavantage.co/query"

_last_av_request_at = 0.0

def _wait_for_av_rate_limit(min_interval: float = 1.0) -> None:
    """Alpha Vantage 免费版约 1 次/秒，两次请求之间至少间隔 min_interval 秒。"""
    global _last_av_request_at
    now = time.monotonic()
    wait = min_interval - (now - _last_av_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_av_request_at = time.monotonic()

def fetch_av_close_on_date(ticker: str, day, api_key: str = ALPHA_VANTAGE_API_KEY) -> float | None:
    """
    从 Alpha Vantage TIME_SERIES_DAILY 取指定交易日的 close。
    day: datetime.date 或 datetime
  """
    if hasattr(day, "date"):
        day = day.date()
    date_str = day.strftime("%Y-%m-%d")

    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "apikey": api_key,
        "outputsize": "compact",  # 最近约100个交易日，够覆盖20天窗口
    }
    url = f"{AV_BASE_URL}?{urlencode(params)}"

    _wait_for_av_rate_limit(10.0)

    with urlopen(url, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    if "Note" in payload or "Information" in payload:
        print(f"Alpha Vantage 限流/提示: {ticker} -> {payload.get('Note') or payload.get('Information')}")
        return None
    if "Error Message" in payload:
        print(f"Alpha Vantage 错误: {ticker} -> {payload['Error Message']}")
        return None

    series = payload.get("Time Series (Daily)")
    if not series:
        print(f"Alpha Vantage 无日线数据: {ticker}")
        return None

    row = series.get(date_str)
    if not row:
        print(f"Alpha Vantage 无 {date_str} 行情: {ticker}")
        return None

    return float(row["4. close"])

def resolve_group_label(
    entry: dict,
    group_key: str,
    *,
    fallback_key: str | None = None,
) -> str:
    """取分组名；空/NaN 时用 fallback_key，再不行用 market。"""
    val = entry.get(group_key)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        val = None
    elif isinstance(val, str) and not val.strip():
        val = None

    if val is None and fallback_key:
        val = entry.get(fallback_key)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        val = entry.get("market", "UNKNOWN")
    return str(val)


def aggregate_daily_pnl(
    daily_pnl_data: list[dict],
    group_key: str,
    *,
    pnl_key: str = "daily_pnl",
    fallback_key: str | None = None,
) -> dict[str, float]:
    """按 group_key 汇总 daily_pnl，返回 {分组名: 盈亏}。"""
    totals: defaultdict[str, float] = defaultdict(float)
    for entry in daily_pnl_data:
        label = resolve_group_label(entry, group_key, fallback_key=fallback_key)
        totals[label] += entry[pnl_key]
    return dict(totals)

def is_weekend(date_obj: datetime.date) -> bool:
    """
    Return True if date_obj is Saturday or Sunday, else False.
    """
    return date_obj.weekday() >= 5

def resolve_latest_prev_day(hist_data: pd.DataFrame, target_date: datetime, prev_date: datetime, ticker: str):
    """
    从 hist_data 中解析 latest_date 与 prev_day，并校验 prev_day 是否等于期望 prev_date（仅比较年月日）

    Returns:
        tuple: (latest_date, prev_day, ok)
            - latest_date/pred_day 为 Timestamp 或 None
            - ok: bool，表示是否通过 prev_date 校验
    """
    if len(hist_data.index) < 2:
        return None, None, False

    latest_date = hist_data.index[-1]
    if latest_date.date() != target_date.date() and not is_weekend(target_date.date()):
        prev_day = hist_data.index[-1]
    else:
        prev_day = hist_data.index[-2]

    if prev_date.date() != prev_day.date():
        print(
            f"警告：yfinance {ticker} 的 prev_day 为 {prev_day.date()}，"
            f"与期望的 prev_date {prev_date.date()} 不一致"
        )
        return latest_date, prev_day, False

    return latest_date, prev_day, True

class Calculator:
    """
    计算器类，用于处理投资组合相关的计算
    """
    
    def __init__(self):
        """
        初始化计算器类
        """
        pass
    
    def calculate_positions(self, trades_df: pd.DataFrame, dvd_df: pd.DataFrame ) -> tuple[
        dict[Any, Any], dict[Any, Any]]:
        """
        计算当前持仓
        
        Args:
            trades_df: 交易数据DataFrame
            
        Returns:
            字典，包含每个市场的持仓信息
        """
        markets = trades_df['Market'].unique()
        current_positions = {}
        closed_positions = {}

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
            average_fx = consideration / cost if (trades_df[trades_df['Market'] == market]['Currency'].iloc[0] == 'USD' and position >0) else 1
            if position != 0:
                # 该 market 下所有 dvd 的 PL Amount 之和
                dvd_pl_total = dvd_df.loc[dvd_df['MarketName'] == market, 'PL Amount'].sum()
                current_positions[market] = {
                    'position': position,
                    'cost': cost,
                    'ccy': trades_df[trades_df['Market'] == market]['Currency'].iloc[0],
                    'initial_fx_rate': initial_fx_rate,
                    'initial_settlement_date': initial_settlement_date,
                    'last_buy_date': market_trades[market_trades['Direction'] == 'BUY'].iloc[-1]['TextDate'] if len(
                        market_trades[market_trades['Direction'] == 'BUY']) > 0 else None,
                    'trade_price': consideration / position,
                    'consideration': consideration,
                    'asset_type': trades_df[trades_df['Market'] == market]['AssetType'].iloc[0],
                    'regions': trades_df[trades_df['Market'] == market]['Region'].iloc[0],
                    'strategy': trades_df[trades_df['Market'] == market]['Strategy'].iloc[0],
                    'average_fx': average_fx,
                    'dvd_pl_total': dvd_pl_total
                }
            else:
                dvd_pl_total = dvd_df.loc[dvd_df['MarketName'] == market, 'PL Amount'].sum()
                closed_positions[market] = {
                    'dvd_pl_total': dvd_pl_total
                }
        return current_positions, closed_positions

    def calculate_market_values(self, current_positions: Dict[str, Dict[str, float]],
                              market_ticker_map: Dict[str, str],
                              target_date: datetime,
                              prev_date :datetime,
                              GBPUSD_FX: float,
                              GBPUSD_FX_prev: float,
                              market_comp_rtn) -> Tuple[List[Dict], float, float, float, datetime]:
        """
        计算市场价值和盈亏

        Args:
            current_positions: 当前持仓信息
            market_ticker_map: 市场代码映射
            target_date: 目标日期
            GBPUSD_FX: 当前GBP/USD汇率
            GBPUSD_FX_prev: 前一日GBP/USD汇率

        Returns:
            (每日盈亏数据, 总市值, 总盈亏, 总成本, 最新日期)
        """
        daily_pnl_data = []
        total_market_value = 0
        total_pnl = 0
        total_cost = 0

        # 初始化货币市值统计
        total_market_value_usd = 0
        total_market_value_gbp = 0

        api_key = ALPHA_VANTAGE_API_KEY
        
        for market, position in current_positions.items():
            if market in market_ticker_map:
                ticker = market_ticker_map[market]
                try:
                    stock = yf.Ticker(ticker)
                    hist_data = stock.history(start=(target_date - pd.Timedelta(days=5)), end=target_date)

                    if len(hist_data.index) >= 2:
                        latest_date, prev_day, ok = resolve_latest_prev_day(hist_data, target_date, prev_date, ticker)
                        if latest_date is None:
                            print(f"{ticker}没有{latest_date}价格数据")
                            continue

                        current_price = float(hist_data.loc[latest_date, 'Close'])
                        if not ok:
                            # print(
                            #     f"yfinance 无 {prev_date.date()} 的 T-1 价格 ({ticker}, "
                            #     f"yfinance prev_day={prev_day.date()})，改用 Alpha Vantage"
                            # )
                            # prev_price = fetch_av_close_on_date(ticker, prev_date, api_key)
                            continue
                        else:
                            prev_price = float(hist_data.loc[prev_day, 'Close'])

                        # 检查是否有分红
                        dividend = float(hist_data.loc[latest_date, 'Dividends']) if 'Dividends' in hist_data.columns else 0
                        if dividend > 0:
                            print(f"{market} 今日分红: {dividend:.4f}")

                        # 将分红计入价格变动
                        price_change = (current_price - prev_price + dividend)

                        # 计算持有时间
                        holding_days_latest = None
                        if position['last_buy_date'] is not None:
                            holding_days_latest = (latest_date.date() - position['last_buy_date'].date()).days

                        # 价格调整
                        # todo find a better way to treat below ticker price adj
                        if position['ccy'] == 'GBP' and ticker not in {'INXG.L', 'IDTG.L', 'GOVP.L', 'ERNS.L', 'IJPH.L', 'GSPX.L', 'GIGB.L', 'DFND.L', 'STHS.L'}:
                            current_price /= 100
                            prev_price /= 100
                            price_change /= 100
                            dividend /= 100

                        # 计算市值和盈亏
                        if position['ccy'] == 'USD':
                            market_value = current_price * position['position'] / GBPUSD_FX
                            total_market_value_usd += current_price * position['position']
                            non_fx_pnl = price_change * position['position'] / GBPUSD_FX
                            fx_change = (1 / GBPUSD_FX - 1 / GBPUSD_FX_prev)
                            fx_pnl = (current_price * position['position']) * fx_change
                            daily_pnl = non_fx_pnl + fx_pnl
                        else:
                            market_value = current_price * position['position']
                            total_market_value_gbp += market_value
                            daily_pnl = price_change * position['position']
                            fx_pnl = 0
                            non_fx_pnl = daily_pnl

                        pnl = market_value - position['cost'] + position['dvd_pl_total']
                        # 计算bps时也要考虑分红的影响
                        bps_change = (price_change / prev_price) * 10000

                        # 计算累计外汇盈亏
                        cumulative_fx_return = 0
                        cumulative_fx_pnl = 0
                        if position['ccy'] != 'GBP' and position['average_fx'] is not None:
                            cumulative_fx_return = (position['average_fx'] / GBPUSD_FX - 1) * 100
                            if position['ccy'] != 'GBP':
                                cumulative_fx_pnl = (position['consideration'] - current_price * position[
                                    'position']) / GBPUSD_FX - (position['cost'] - market_value)

                        # 更新总计
                        total_market_value += market_value
                        total_pnl += pnl
                        total_cost += position['cost']
                        cumulative_dividend = current_positions[market]['dvd_pl_total']
                        spx_rtn = market_comp_rtn["^GSPC"]
                        bench_rtn = market_comp_rtn["ES=F"] if spx_rtn == 0 else spx_rtn
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
                            'trade_price': position['trade_price'],
                            'asset_type': position['asset_type'],
                            'region': position['regions'],
                            "Strategy": (market if pd.isna(position.get("strategy")) else position.get("strategy")),
                            'cumulative dividend': cumulative_dividend,
                            'S&P 500 daily return': bench_rtn
                        })
                    else:
                        print(f"获取{ticker}数据时不足2天")
                except Exception as e:
                    print(f"获取{ticker}数据时发生错误: {e}")
        region_pnl = aggregate_daily_pnl(daily_pnl_data, "region")
        region_market_value = aggregate_daily_pnl(daily_pnl_data, "region", pnl_key = 'market_value')
        strategy_pnl = aggregate_daily_pnl(
            daily_pnl_data, "Strategy", fallback_key="market"
        )
        strategy_market_value = aggregate_daily_pnl(daily_pnl_data, "Strategy", pnl_key = 'market_value', fallback_key="market")

        return (
            daily_pnl_data,
            total_market_value,
            total_pnl,
            total_cost,
            region_pnl,
            region_market_value,
            strategy_pnl,
            strategy_market_value,
            total_market_value_usd,
            total_market_value_gbp,
        )

    def calculate_realized_pnl(self, trades_df: pd.DataFrame, markets: List[str], realized_positions) -> float:
        """
        计算已实现盈亏

        Args:
            trades_df: 交易数据DataFrame
            markets: 市场列表

        Returns:
            已实现盈亏
        """
        realized_pnl = 0
        for market in markets:
            market_trades = trades_df[trades_df['Market'] == market]
            closed_positions = market_trades[market_trades['Direction'] == 'SELL']
            if any(closed_positions['Activity'] == 'CORPORATE ACTION'):
                closed_positions = closed_positions[closed_positions['Activity'] != 'CORPORATE ACTION']
                # print(f"{market}市场存在Corporate actions，跳过pnl计算")

            if not closed_positions.empty:
                trade_pnl = 0
                dvd = 0.0
                if market in realized_positions and isinstance(realized_positions[market], dict):
                    dvd = realized_positions[market].get('dvd_pl_total', 0.0)
                buy_trades = market_trades[
                    (market_trades['TextDate'] <= closed_positions['TextDate'].max()) &
                    (market_trades['Direction'] == 'BUY')
                    ].sort_values('TextDate')
                if buy_trades.empty:
                    continue
                if any(buy_trades['Activity'] == 'CORPORATE ACTION'):
                    valid_quantities = buy_trades.loc[buy_trades['Activity'] == 'CORPORATE ACTION', 'Quantity'].iloc[0]
                    buy_trades['Quantity'] = valid_quantities
                    buy_trades = buy_trades[buy_trades['Activity'] != 'CORPORATE ACTION']
                remaining_quantity = -closed_positions['Quantity'].sum()
                position = 0
                for _, buy_trade in buy_trades.iterrows():
                    if remaining_quantity <= 0:
                        break
                    if buy_trade['Quantity'] <= remaining_quantity:
                        remaining_quantity -= buy_trade['Quantity']
                        position += 1
                    else:
                        position = position + remaining_quantity/buy_trade['Quantity']
                        remaining_quantity = 0

                # 计算buy_trades的Cost/Proceeds，考虑position的小数部分
                buy_trades_pnl = 0
                position_int = int(position)
                position_frac = position - position_int  # 小数部分
                
                # 保留前position_int行
                if position_int > 0:
                    buy_trades_pnl += float(buy_trades['Cost/Proceeds'].iloc[:position_int].sum())
                
                # 如果有小数部分，处理第position_int行（索引从0开始，所以是position_int）
                if position_frac > 0 and position_int < len(buy_trades):
                    buy_trades_pnl += float(buy_trades['Cost/Proceeds'].iloc[position_int]) * position_frac
                
                # 计算closed_positions的Cost/Proceeds
                closed_pnl = float(closed_positions['Cost/Proceeds'].sum())
                
                trade_pnl += closed_pnl + buy_trades_pnl + dvd

                if remaining_quantity > 0:
                    print(f"警告：{market}市场的卖出数量大于之前的买入数量")
                realized_pnl += trade_pnl

        return realized_pnl

    def calculate_global_indices_return(self, target_date: datetime) -> Tuple[Dict[str, float], Dict[str, datetime]]:
        """
        计算全球主要指数的当日回报率

        Args:
            target_date: 目标日期

        Returns:
            (指数回报率字典, 最新日期字典)
        """
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

    @staticmethod
    def asset_type_calc(daily_pnl):
        from collections import defaultdict
        asset_totals = defaultdict(float)
        total_market_value = 0.0
        for entry in daily_pnl:
            asset_type = entry['asset_type']
            market_value = entry['market_value']
            asset_totals[asset_type] += market_value
            total_market_value += market_value
        asset_type_pct = []
        for asset_type, value in asset_totals.items():
            pct = value / total_market_value if total_market_value != 0 else 0
            asset_type_pct.append({'asset_type': asset_type, 'percentage': pct})
        return asset_type_pct

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
        positions = Calculator().calculate_positions(trades_df)
        print("\n当前持仓:")
        print(positions)

        # 测试市场价值计算
        market_ticker_map = get_market_ticker_map(trades_df, enum_df)
        from datetime import datetime

        daily_pnl_data, total_mv, total_pnl, total_cost, latest_date = Calculator().calculate_market_values(
            positions, market_ticker_map, datetime.today(), 1.27, 1.26)

        print(f"\n总市值: {total_mv:,.2f}")
        print(f"总盈亏: {total_pnl:,.2f}")

        # 测试已实现盈亏计算
        realized_pnl = Calculator().calculate_realized_pnl(trades_df, trades_df['Market'].unique())
        print(f"已实现盈亏: {realized_pnl:,.2f}")

        # 测试全球指数回报率计算
        indices_returns, indices_dates = Calculator().calculate_global_indices_return(datetime.today())
        print("\n全球主要指数回报率:")
        for index_name, return_bps in indices_returns.items():
            if return_bps is not None:
                print(f"{index_name}: {return_bps:.2f}bps ({indices_dates[index_name].strftime('%Y-%m-%d')})")