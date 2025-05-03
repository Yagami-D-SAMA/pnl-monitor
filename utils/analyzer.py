import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from typing import Dict, List, Tuple, Optional, Union
from .calculator import (
    calculate_positions,
    calculate_market_values,
    calculate_realized_pnl,
    calculate_global_indices_return
)
from .DataLoader import DataLoader
from .Calculator import Calculator
from .report_generator import generate_report

def analyze_portfolio(data_source: str = 'ALL') -> None:
    """
    分析投资组合
    
    Args:
        data_source: 数据源，默认为'ALL'
    """
    # 设置投资目录
    investment_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'investment_data')
    
    # 检查必要的文件
    required_files = ['trades.csv', 'market_ticker_map.csv']
    for file in required_files:
        if not os.path.exists(os.path.join(investment_dir, file)):
            raise FileNotFoundError(f"Required file {file} not found in {investment_dir}")
    
    # 创建DataLoader实例
    data_loader = DataLoader(investment_dir)
    
    # 加载交易数据
    trades_df = data_loader.load_trade_data()
    
    # 获取市场代码映射
    market_ticker_map = data_loader.get_market_ticker_mapping()
    
    # 计算当前持仓
    positions = calculate_positions(trades_df)
    
    # 获取目标日期
    target_date = datetime.now()
    
    # 获取GBP/USD汇率
    GBPUSD_FX = 1.25  # 示例值，实际应从数据源获取
    GBPUSD_FX_prev = 1.24  # 示例值，实际应从数据源获取
    
    # 计算市场价值和盈亏
    daily_pnl_df, total_mv, total_pnl, total_cost, latest_date = calculate_market_values(
        positions, market_ticker_map, target_date, GBPUSD_FX, GBPUSD_FX_prev)
    
    # 计算已实现盈亏
    markets = list(positions.keys())
    realized_pnl = calculate_realized_pnl(trades_df, markets)
    
    # 计算全球指数回报率
    indices_returns, indices_dates = calculate_global_indices_return(target_date)
    
    # 打印结果
    print(f"\n投资组合分析结果 ({latest_date.strftime('%Y-%m-%d')}):")
    print(f"总市值: {total_mv:,.2f}")
    print(f"总盈亏: {total_pnl:,.2f}")
    print(f"总成本: {total_cost:,.2f}")
    print("\n各市场表现:")
    print(daily_pnl_df.to_string())
    print("\n已实现盈亏:")
    for market, pnl in realized_pnl.items():
        print(f"{market}: {pnl:,.2f}")
    print("\n全球指数回报率:")
    for index, ret in indices_returns.items():
        print(f"{index}: {ret:.2f}%")

def load_historical_pnl(target_date: str, data_source: str = 'ALL') -> None:
    """
    加载历史盈亏数据
    
    Args:
        target_date: 目标日期
        data_source: 数据源，默认为'ALL'
    """
    # 实现历史盈亏数据加载逻辑
    pass

def calculate_cumulative_contribution(start_date: str, end_date: str, data_source: str = 'ALL') -> None:
    """
    计算累计贡献度
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        data_source: 数据源，默认为'ALL'
    """
    # 实现累计贡献度计算逻辑
    pass

def run_historical_analysis(target_date: str) -> None:
    """
    运行历史分析
    
    Args:
        target_date: 目标日期
    """
    # 实现历史分析逻辑
    pass

def analyze_portfolio_old(target_date: object = None, data_source: object = 'SXAFI') -> object:
    """主函数：分析投资组合"""
    # 设置目标日期
    if target_date is None:
        target_date = datetime.today()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d')

    # 设置文件路径
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    investment_dir = os.path.join(base_dir, 'investment')
    
    # 根据数据源选择交易历史文件
    if data_source == 'ALL':
        trade_history_paths = [
            os.path.join(investment_dir, 'TradeHistory-SXAFI-(01-03-2017)-(02-03-2025).csv'),
            os.path.join(investment_dir, 'TradeHistory-SX9Q9-(03-03-2017)-(02-03-2025).csv')
        ]
    else:
        trade_history_paths = [os.path.join(investment_dir, f'TradeHistory-{data_source}-(01-03-2017)-(02-03-2025).csv')]
    
    enum_path = os.path.join(investment_dir, 'enum.csv')
    
    # 检查文件是否存在
    for path in trade_history_paths:
        if not os.path.exists(path):
            print(f"错误：交易历史文件不存在 - {path}")
            return
    if not os.path.exists(enum_path):
        print(f"错误：枚举文件不存在 - {enum_path}")
        return
    
    try:
        # 创建DataLoader和Calculator实例
        data_loader = DataLoader(investment_dir)
        calculator = Calculator()
        
        # 加载数据
        trades_df, enum_df = data_loader.load_trade_data(trade_history_paths, enum_path, target_date)
        if trades_df is None or enum_df is None:
            return
            
        # 获取市场和ticker映射
        market_ticker_map = data_loader.get_market_ticker_map()
        
        # 计算持仓
        current_positions = calculator.calculate_positions(trades_df)
        
        # 获取汇率数据
        GBPUSD_FX, GBPUSD_FX_prev = DataLoader.get_fx_rates(target_date)
        
        # 计算市场价值和盈亏
        daily_pnl_data, total_market_value, total_pnl, total_cost, latest_date = calculator.calculate_market_values(
            current_positions, market_ticker_map, target_date, GBPUSD_FX, GBPUSD_FX_prev)

        # 计算已实现盈亏
        realized_pnl = calculator.calculate_realized_pnl(trades_df, trades_df['Market'].unique())
        
        # 生成报告
        daily_pnl_result = generate_report(
            daily_pnl_data, total_market_value, total_pnl, total_cost, realized_pnl, latest_date)
            
        # 保存结果
        data_loader.save_results(daily_pnl_result, trade_history_paths)
        
    except Exception as e:
        print(f"分析过程中发生错误: {e}")

def calculate_cumulative_contribution_old(start_date_str, end_date_str, data_source='ALL'):
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
                    contribution = (daily_pnl_result['total_daily_pnl'] / daily_pnl_result['total_market_value']) * 10000
                    daily_contributions.append(contribution)
                    fx_contribution = (daily_pnl_result['total_fx_pnl'] / daily_pnl_result['total_market_value']) * 10000
                    daily_fx_contributions.append(fx_contribution)
                    
                    # 累计盈亏
                    total_pnl += daily_pnl_result['total_daily_pnl']
                    total_fx_pnl += daily_pnl_result['total_fx_pnl']
                    total_non_fx_pnl += daily_pnl_result['total_non_fx_pnl']
                    
                    print(f"{date.strftime('%Y-%m-%d'):<12} {contribution:>15,.2f} "
                          f"{daily_pnl_result['total_daily_pnl']:>15,.2f} "
                          f"{daily_pnl_result['total_fx_pnl']:>20,.2f} "
                          f"{daily_pnl_result['total_non_fx_pnl']:>20,.2f} "
                          f"{daily_pnl_result['total_market_value']:>20,.2f}")
        
        print("-" * 120)
        if daily_contributions:
            cumulative_contribution = sum(daily_contributions)
            cumulative_fx_contribution = sum(daily_fx_contributions)
            print(f"\n汇总信息:")
            print("-" * 80)
            print(f"期间累计总贡献度: {cumulative_contribution:>15,.2f} bps")
            print(f"期间外汇累计贡献度: {cumulative_fx_contribution:>12,.2f} bps")
            print(f"期间总盈亏: {total_pnl:>20,.2f} GBP")
            print(f"期间外汇盈亏: {total_fx_pnl:>18,.2f} GBP")
            # print(f"期间非外汇盈亏: {total_non_fx_pnl:>15,.2f} GBP")
            print("-" * 80)
        else:
            print("在指定日期范围内没有找到数据")
        
    except Exception as e:
        print(f"计算累计贡献度时发生错误: {e}")

def run_historical_analysis_old(start_date_str='2025-01-01', end_date_str = '2025-01-02'):
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