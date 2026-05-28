import pandas as pd
from datetime import datetime, timedelta
import os
import pickle
from tabulate import tabulate
import yfinance as yf
from utils.Calculator import is_weekend
from pathlib import Path
import re
from utils.ticker_harvest import read_h5, OUTPUT_DIR, H5_KEY
from utils.FundamentalData import fetch_earnings_batch
from datetime import date, datetime, timedelta

BANK_HOLIDAYS: set[date] = {
    date(2026, 5, 25),
    # date(2025, 12, 25),  # 示例：按需添加
}
def is_bank_holiday(d: date) -> bool:
    return d in BANK_HOLIDAYS
def is_business_day(d: date) -> bool:
    return not is_weekend(d) and not is_bank_holiday(d)

# def get_previous_business_day(target_date: datetime) -> datetime:
#     # 先从前一天开始
#     prev_date = target_date - timedelta(days=1)
#
#     # 如果是周末，就一直往前减一天，直到不是周末
#     while is_weekend(prev_date.date()):
#         prev_date -= timedelta(days=1)
#
#     return prev_date

def get_previous_business_day(target_date: datetime) -> datetime:
    prev_date = target_date - timedelta(days=1)
    while not is_business_day(prev_date.date()):
        prev_date -= timedelta(days=1)
    return prev_date

def analyze_portfolio(target_date: object = None, data_source: object = None, asset_type: bool = True) -> object:
    """主函数：分析投资组合"""
    # 设置目标日期
    if target_date is None:
        target_date = datetime.today()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d')
    # force time to 23:30 each day
    target_date = target_date.replace(hour=23, minute=30, second=0, microsecond=0)
    prev_date = get_previous_business_day(target_date)

    # 设置文件路径
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    investment_dir = os.path.join(base_dir, 'investment')
    trade_history_path_SXAFI = os.path.join(investment_dir, 'TradeHistory-SXAFI.csv')
    trade_history_path_SX9Q9 = os.path.join(investment_dir, 'TradeHistory-SX9Q9.csv')
    dvd_history_path = os.path.join(investment_dir, 'DvdHistory.csv')
    enum_path = os.path.join(investment_dir, 'enum.csv')

    # 确定要处理的文件
    trade_history_paths = []
    if data_source == 'SXAFI':
        trade_history_paths.append(trade_history_path_SXAFI)
    elif data_source == 'SX9Q9':
        trade_history_paths.append(trade_history_path_SX9Q9)
    elif data_source == 'ALL':
        trade_history_paths.extend([trade_history_path_SXAFI, trade_history_path_SX9Q9])
    else:
        print(f"错误：无效的数据源选择 {data_source}，请使用 'SXAFI'、'SX9Q9' 或 'ALL'")
        return

    # 检查文件是否存在
    for path in trade_history_paths:
        if not os.path.exists(path):
            print(f"错误：无法找到交易历史文件 - {path}")
            return
    if not os.path.exists(enum_path):
        print(f"错误：无法找到枚举文件 - {enum_path}")
        return
    if not os.path.exists(dvd_history_path):
        print(f"错误：无法找到枚举文件 - {dvd_history_path}")
        return

    try:
        # 加载数据
        from . import generate_report
        from . import DataLoader
        from . import Calculator
        data_loader = DataLoader(investment_dir, trade_history_paths, enum_path, dvd_history_path, target_date)
        trades_df, enum_df, dvd_df  = data_loader.load_trade_data()
        if trades_df is None or enum_df is None or dvd_df is None:
            return
        # 获取市场和ticker映射
        market_ticker_map = data_loader.get_market_ticker_map()
        # 计算持仓
        calculator = Calculator()
        current_positions, closed_positions = calculator.calculate_positions(trades_df, dvd_df)
        # 获取汇率数据
        GBPUSD_FX, GBPUSD_FX_prev = data_loader.get_fx_rates(target_date)
        market_comp_rtn = data_loader.get_market_comp_rtn(target_date,['^GSPC', 'ES=F'], prev_date)
        # 计算市场价值和盈亏
        daily_pnl_data, total_market_value, total_pnl, total_cost, region_pnl, region_market_value, strategy_pnl, strategy_market_value, total_market_value_usd, \
            total_market_value_gbp = calculator.calculate_market_values(current_positions, market_ticker_map,
                                                                        target_date, prev_date, GBPUSD_FX, GBPUSD_FX_prev, market_comp_rtn)
        # 计算已实现盈亏
        realized_pnl = calculator.calculate_realized_pnl(trades_df, trades_df['Market'].unique(), closed_positions)
        if asset_type:
            asset_type_pct = calculator.asset_type_calc(daily_pnl_data)
            table_data = [
                [entry['asset_type'], f"{entry['percentage'] * 100:.2f}%"]
                for entry in asset_type_pct
            ]
            print(tabulate(table_data, headers=["Asset Type", "Market Value %"], tablefmt="fancy_grid"))
        
        # 显示货币市值分布和汇率信息
        print("\n货币市值分布:")
        
        # 计算百分比
        usd_gbp_value = total_market_value_usd / GBPUSD_FX
        usd_percentage = (usd_gbp_value / total_market_value) * 100 if total_market_value > 0 else 0
        gbp_percentage = (total_market_value_gbp / total_market_value) * 100 if total_market_value > 0 else 0
        gbp_usd_bps = (GBPUSD_FX - GBPUSD_FX_prev) * 10000
        
        currency_data = [
            ["USD市值", f"{total_market_value_usd:,.2f}", "USD"],
            ["USD资产(GBP)", f"{usd_gbp_value:,.2f}", "GBP"],
            ["USD资产%", f"{usd_percentage:.2f}%", ""],
            ["GBP市值", f"{total_market_value_gbp:,.2f}", "GBP"],
            ["GBP资产%", f"{gbp_percentage:.2f}%", ""],
            ["总市值", f"{total_market_value:,.2f}", "GBP"],
            ["当日GBP/USD", f"{GBPUSD_FX:.4f}", ""],
            ["当日GBP/USD move", f"{gbp_usd_bps:.4f}", "bps"]
        ]
        print(tabulate(currency_data, headers=["项目", "数值", "单位"], disable_numparse=[0, 1, 2]))
        
        # 生成报告
        daily_pnl_result = generate_report(
            daily_pnl_data, total_market_value, total_pnl, total_cost, realized_pnl, target_date, region_pnl, region_market_value, strategy_pnl, strategy_market_value)
        # 保存结果
        data_loader.save_results(daily_pnl_result, trade_history_paths)

    except Exception as e:
        print(f"分析过程中发生错误: {e}")


def load_historical_pnl(target_date_str, data_source='ALL'):
    """加载指定日期的PnL数据"""
    try:
        # 转换日期格式
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
        formatted_date = target_date.strftime('%Y%m%d')

        # 设置文件路径
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        investment_dir = os.path.join(base_dir, 'investment')
        daily_pnl_dir = os.path.join(investment_dir, 'Daily Pnl')

        # 构建文件名模式
        if data_source == 'ALL':
            file_pattern = f'daily_pnl_SXAFI_SX9Q9_{formatted_date}.pkl'
        else:
            file_pattern = f'daily_pnl_{data_source}_{formatted_date}.pkl'

        pnl_file = os.path.join(daily_pnl_dir, file_pattern)

        if not os.path.exists(pnl_file):
            print(f"错误：找不到{target_date_str}的PnL数据文件")
            return

        # 读取pkl文件
        with open(pnl_file, 'rb') as f:
            daily_pnl_result = pickle.load(f)

        # 生成报告
        from . import generate_report

        market_details = daily_pnl_result['market_details']
        total_market_value = daily_pnl_result['total_market_value']
        total_cost = sum(data['cost'] for data in market_details)
        total_pnl = sum(data['pnl'] for data in market_details)
        realized_pnl = daily_pnl_result['realized_pnl']  # 历史数据中没有已实现盈亏信息
        regional_pnl = daily_pnl_result.get('regional_pnl')

        generate_report(market_details, total_market_value, total_pnl, total_cost, realized_pnl,
                        daily_pnl_result['date'], regional_pnl)

    except Exception as e:
        print(f"加载历史数据时发生错误: {e}")


def calculate_cumulative_contribution(start_date_str, end_date_str, data_source='ALL'):
    """计算指定日期范围内的累计贡献度和盈亏"""
    try:
        # 转换日期格式
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        date_range = pd.date_range(start=start_date, end=end_date)

        # 设置文件路径
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        investment_dir = os.path.join(base_dir, 'investment')
        daily_pnl_dir = os.path.join(investment_dir, 'Daily Pnl')

        # 存储每日数据
        daily_contributions = []
        daily_fx_contributions = []
        total_pnl = 0
        total_fx_pnl = 0
        total_non_fx_pnl = 0
        
        # 存储所有日期的数据
        all_daily_data = []

        # 定义指数列表
        indices = {
            "MSCI World": "URTH",
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
        # 获取GBPUSD汇率数据
        try:
            gbpusd_ticker = yf.Ticker("GBPUSD=X")
            gbpusd_data = gbpusd_ticker.history(start=start_date - pd.Timedelta(days=1), end=end_date + pd.Timedelta(days=1))
            if not gbpusd_data.empty:
                gbpusd_start = gbpusd_data['Close'].iloc[0]
                gbpusd_end = gbpusd_data['Close'].iloc[-1]
                gbpusd_change = gbpusd_end - gbpusd_start
                gbpusd_bps = gbpusd_change * 10000
                print(f"\nGBP/USD汇率变化 ({start_date_str} 至 {end_date_str}):")
                print("-" * 60)
                print(f"起始汇率: {gbpusd_start:.4f}")
                print(f"结束汇率: {gbpusd_end:.4f}")
                print(f"汇率变化(bps): {gbpusd_bps:+.2f} bps")
                print("-" * 60)
            else:
                print("无法获取GBP/USD汇率数据")
        except Exception as e:
            print(f"获取GBP/USD汇率数据时发生错误: {e}")
        
        # 计算指数累计回报率
        index_returns = {}
        for index_name, ticker in indices.items():
            try:
                index = yf.Ticker(ticker)
                hist_data = index.history(start=start_date - pd.Timedelta(days=1), end=end_date + pd.Timedelta(days=1))
                
                if len(hist_data.index) >= 2:
                    start_price = float(hist_data.loc[hist_data.index[0], 'Close'])
                    end_price = float(hist_data.loc[hist_data.index[-1], 'Close'])
                    total_return = ((end_price / start_price) - 1) * 100
                    index_returns[index_name] = total_return
                else:
                    index_returns[index_name] = None
            except Exception as e:
                print(f"获取{index_name}指数数据时发生错误: {e}")
                index_returns[index_name] = None

        print(f"\n{start_date_str}至{end_date_str}的盈亏分析:")
        print("-" * 120)
        print(f"{'日期':<12} {'当日贡献度(bps)':>15} {'当日总盈亏(GBP)':>15} {'当日外汇盈亏(GBP)':>15} "
              f"{'当日非外汇盈亏(GBP)':>15} {'当日总市值(GBP)':>15}")
        print("-" * 120)

        for date in date_range:
            formatted_date = date.strftime('%Y%m%d')

            # 构建文件名
            if data_source == 'ALL':
                file_pattern = f'daily_pnl_SXAFI_SX9Q9_{formatted_date}.pkl'
            else:
                file_pattern = f'daily_pnl_{data_source}_{formatted_date}.pkl'

            pnl_file = os.path.join(daily_pnl_dir, file_pattern)

            if os.path.exists(pnl_file):
                with open(pnl_file, 'rb') as f:
                    daily_pnl_result = pickle.load(f)

                if daily_pnl_result['total_market_value'] != 0:
                    contribution = (daily_pnl_result['total_daily_pnl'] / daily_pnl_result[
                        'total_market_value']) * 10000
                    daily_contributions.append(contribution)
                    fx_contribution = (daily_pnl_result['total_fx_pnl'] / daily_pnl_result[
                        'total_market_value']) * 10000
                    daily_fx_contributions.append(fx_contribution)

                    # 累计盈亏
                    total_pnl += daily_pnl_result['total_daily_pnl']
                    total_fx_pnl += daily_pnl_result['total_fx_pnl']
                    total_non_fx_pnl += daily_pnl_result['total_non_fx_pnl']
                    
                    # 存储每日数据
                    all_daily_data.append({
                        'date': date,
                        'contribution': contribution,
                        'total_daily_pnl': daily_pnl_result['total_daily_pnl'],
                        'total_fx_pnl': daily_pnl_result['total_fx_pnl'],
                        'total_non_fx_pnl': daily_pnl_result['total_non_fx_pnl'],
                        'total_market_value': daily_pnl_result['total_market_value']
                    })

        # 只显示最近10天的数据
        recent_data = all_daily_data[-10:] if len(all_daily_data) > 10 else all_daily_data
        
        # 打印最近10天的数据
        for data in recent_data:
            print(f"{data['date'].strftime('%Y-%m-%d'):<12} {data['contribution']:>15,.2f} "
                  f"{data['total_daily_pnl']:>15,.2f} "
                  f"{data['total_fx_pnl']:>20,.2f} "
                  f"{data['total_non_fx_pnl']:>20,.2f} "
                  f"{data['total_market_value']:>20,.2f}")

        print("-" * 120)
        if daily_contributions:
            cumulative_contribution = sum(daily_contributions)
            cumulative_fx_contribution = sum(daily_fx_contributions)
            days_held = (end_date - start_date).days
            T = days_held / 365.25
            annualized_return = ((1 + cumulative_contribution/10000) ** (1 / T) - 1) * 100# accounting for leap years
            print(f"\n汇总信息:")
            print("-" * 80)
            print(f"期间累计总贡献度: {cumulative_contribution:>15,.2f} bps")
            print(f"年化总贡献度: {annualized_return:>15,.2f}%")
            print(f"期间外汇累计贡献度: {cumulative_fx_contribution:>12,.2f} bps")
            print(f"期间非外汇累计贡献度: {cumulative_contribution - cumulative_fx_contribution:>12,.2f} bps")
            print(f"期间总盈亏: {total_pnl:>20,.2f} GBP")
            print(f"期间外汇盈亏: {total_fx_pnl:>18,.2f} GBP")
            print(f"期间盈亏: {total_pnl - total_fx_pnl:>18,.2f} GBP")
            print("-" * 80)
            
            # 打印指数累计回报率
            print("\n全球主要指数累计回报率:")
            print("-" * 80)
            print(f"{'指数名称':<30} {'累计回报率(%)':>15}")
            print("-" * 80)
            for index_name, return_rate in sorted(index_returns.items(), key=lambda x: x[1] if x[1] is not None else float('-inf'), reverse=True):
                if return_rate is not None:
                    print(f"{index_name:<30} {return_rate:>15,.2f}")
                else:
                    print(f"{index_name:<30} {'N/A':>15}")
            print("-" * 80)
        else:
            print("在指定日期范围内没有找到数据")

    except Exception as e:
        print(f"计算累计贡献度时发生错误: {e}")


def run_historical_analysis(start_date_str='2025-01-01', end_date_str='2025-01-02'):
    """运行历史分析，从指定日期到今天之前的所有工作日"""
    try:
        # 转换日期格式
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        # end_date = datetime.today() - pd.Timedelta(days=1)  # 昨天
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

        # 生成工作日序列
        date_range = pd.date_range(start=start_date, end=end_date)
        business_days = [d for d in date_range if d.weekday() < 5]  # 排除周末

        # 数据源列表
        data_sources = ['ALL']

        print(f"\n开始运行从{start_date_str}到{end_date.strftime('%Y-%m-%d')}的历史分析")
        print("-" * 50)

        total_days = len(business_days)
        total_sources = len(data_sources)
        current_count = 0

        for date in business_days:
            date_str = date.strftime('%Y-%m-%d')
            for source in data_sources:
                current_count += 1
                progress = (current_count / (total_days * total_sources)) * 100
                print(f"\n处理日期: {date_str}, 数据源: {source} (总进度: {progress:.1f}%)")
                analyze_portfolio(date_str, source)

        print("\n历史分析完成！")
        print("-" * 50)

    except Exception as e:
        print(f"运行历史分析时发生错误: {e}")


def stock_monitor(days=30):
    """
    监控watchlist中的股票，计算指定天数的投资组合PnL
    
    Args:
        days: 要分析的天数，默认30天
    """
    import_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    watchlist_path = os.path.join(import_path, 'investment', 'watchlist.pkl')
    
    if not os.path.exists(watchlist_path):
        print("未找到watchlist.pkl，请先创建watchlist。")
        return
    
    # 读取watchlist分配
    with open(watchlist_path, 'rb') as f:
        stock_allocations = pickle.load(f)
    
    print(f"\n投资组合监控结果 (过去{days}天):")
    print("=" * 80)
    
    # 计算总名义金额
    total_notional = sum(data['notional_allocation'] for data in stock_allocations.values())
    print(f"总名义金额: {total_notional:,.2f}")
    print("=" * 80)
    
    # 存储每个股票的数据
    portfolio_data = {}
    total_pnl = 0
    total_return = 0
    
    # 获取GBPUSD汇率数据
    try:
        gbpusd_stock = yf.Ticker("GBPUSD=X")
        gbpusd_data = gbpusd_stock.history(start=(datetime.today() - pd.Timedelta(days=days + 1)), end=datetime.today())
        if not gbpusd_data.empty:
            gbpusd_start = gbpusd_data['Close'].iloc[0].item()
            gbpusd_end = gbpusd_data['Close'].iloc[-1].item()
            gbpusd_change = gbpusd_end - gbpusd_start
            gbpusd_return = (gbpusd_end / gbpusd_start - 1) * 100
            print(f"GBPUSD: {gbpusd_start:.4f} → {gbpusd_end:.4f} {gbpusd_change:>+8.4f} ({gbpusd_return:>+6.2f}%)")
        else:
            print("GBPUSD: 无法获取汇率数据")
    except Exception as e:
        print(f"GBPUSD: 获取汇率数据出错: {e}")
    
    print("-" * 80)
    
    for symbol, allocation_data in stock_allocations.items():
        try:
            # 获取历史价格数据
            stock = yf.Ticker(symbol)
            hist_data = stock.history(start=(datetime.today() - pd.Timedelta(days=days + 1)), end=datetime.today())
            
            # 计算价格变化
            start_price = hist_data['Close'].iloc[0].item()
            end_price = hist_data['Close'].iloc[-1].item()
            price_change = end_price - start_price
            price_return = (end_price / start_price - 1) * 100
            
            # 计算该股票的PnL
            stock_pnl = price_change * (allocation_data['notional_allocation'] / start_price)
            stock_return = price_return * allocation_data['weight']
            
            portfolio_data[symbol] = {
                'start_price': start_price,
                'end_price': end_price,
                'price_change': price_change,
                'price_return': price_return,
                'allocation': allocation_data['notional_allocation'],
                'weight': allocation_data['weight'],
                'pnl': stock_pnl,
                'return_contribution': stock_return
            }
            
            total_pnl += stock_pnl
            total_return += stock_return
            
            print(f"{symbol:<10} {start_price:>8.2f} → {end_price:>8.2f} "
                  f"{price_change:>+8.2f} ({price_return:>+6.2f}%) "
                  f"PnL: {stock_pnl:>10.2f} "
                  f"权重: {allocation_data['weight']:>6.3f}")
                  
        except Exception as e:
            print(f"{symbol:<10} 获取数据出错: {e}")
    
    print("=" * 80)
    print(f"投资组合总PnL: {total_pnl:>10.2f}")
    print(f"投资组合总回报: {total_return:>+6.2f}%")
    print(f"年化回报率: {(total_return / days * 365):>+6.2f}%")
    print("=" * 80)
    
    # 按PnL贡献排序
    if portfolio_data:
        print("\n按PnL贡献排序:")
        sorted_stocks = sorted(portfolio_data.items(), key=lambda x: x[1]['pnl'], reverse=True)
        print(f"{'股票':<10} {'PnL':<12} {'回报贡献':<12} {'权重':<8}")
        print("-" * 50)
        for symbol, data in sorted_stocks:
            print(f"{symbol:<10} {data['pnl']:<12.2f} {data['return_contribution']:<+12.2f}% {data['weight']:<8.3f}")
    
    return portfolio_data, total_pnl, total_return

def parse_ticker_db_date(path: Path) -> datetime:
    """从 tickers_NYSE+NASDAQ_20260514_171332.h5 解析 20260514"""
    m = re.search(r"_(\d{8})_\d{6}\.h5$", path.name)
    if not m:
        raise ValueError(f"无法从文件名解析日期: {path.name}")
    return datetime.strptime(m.group(1), "%Y%m%d")

def stock_value_factor(ticker_h5=None, as_of_date=None, fiscal_year=2025, fiscal_period="q4", limit=None):
    ticker_db = OUTPUT_DIR / "tickers_NYSE+NASDAQ_20260519_165904.h5"
    h5_path = ticker_h5 or ticker_db
    db_as_of = as_of_date or parse_ticker_db_date(h5_path)
    # read_h5 会打印摘要；若不想刷屏，可用下面静默版：
    tickers = pd.read_hdf(h5_path, key=H5_KEY)
    # tickers = read_h5(h5_path)
    # 通常只要上市、普通股
    universe = tickers[
        (tickers["status"] == "Active")
        & (tickers["asset_type"].str.upper() == "STOCK")
    ].copy()
    print(f"Ticker universe as of {db_as_of.date()}: {len(universe):,} symbols")
    symbols = universe["symbol"].tolist()
    earnings_df = fetch_earnings_batch(
        symbols,
        year=fiscal_year,
        period=fiscal_period,
        limit=limit,  # 全市场先别去掉 limit
        sleep_sec=0.25,  # 按你套餐调，避免 429
    )
    # 后续：对 universe["symbol"] 拉估值/earnings（如 API Ninjas）再算 value factor
    return universe, db_as_of, earnings_df



if __name__ == "__main__":
    # 测试分析功能
    print("测试分析模块")

    # 测试投资组合分析
    print("\n1. 测试当前投资组合分析")
    analyze_portfolio(data_source='ALL')

    # 测试历史PnL加载
    print("\n2. 测试历史PnL加载")
    load_historical_pnl('2025-02-28', data_source='ALL')

    # 测试累计贡献度计算
    print("\n3. 测试累计贡献度计算")
    calculate_cumulative_contribution('2025-02-19', '2025-02-28', data_source='ALL')

    # 测试历史分析
    print("\n4. 测试历史分析")
    run_historical_analysis('2025-02-19') 