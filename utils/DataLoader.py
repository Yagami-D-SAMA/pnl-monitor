import pandas as pd
import yfinance as yf
from datetime import datetime
import os
import pickle

class DataLoader:
    def __init__(self, investment_dir=None):
        """初始化DataLoader类
        
        Args:
            investment_dir (str, optional): 投资数据目录路径. Defaults to None.
        """
        self.investment_dir = investment_dir
        self.trades_df = None
        self.enum_df = None
        self.market_ticker_map = None

    def load_trade_data(self, trade_history_paths, enum_path, target_date=None):
        """加载交易数据和枚举数据
        
        Args:
            trade_history_paths (list): 交易历史文件路径列表
            enum_path (str): 枚举数据文件路径
            target_date (str/datetime, optional): 目标日期. Defaults to None.
            
        Returns:
            tuple: (trades_df, enum_df)
        """
        try:
            self.trades_df = pd.concat([pd.read_csv(path) for path in trade_history_paths])
            self.enum_df = pd.read_csv(enum_path)
            
            # 数据预处理
            self.trades_df['Price'] = self.trades_df['Price'] / 100
            self.trades_df['TextDate'] = pd.to_datetime(self.trades_df['TextDate'], format='%d/%m/%Y')
            self.trades_df['TradeValue'] = self.trades_df['Price'] * self.trades_df['Quantity']
            
            # 如果提供了target_date，过滤掉晚于target_date的交易
            if target_date is not None:
                if isinstance(target_date, str):
                    target_date = pd.to_datetime(target_date)
                self.trades_df = self.trades_df[self.trades_df['TextDate'] <= target_date]
            
            return self.trades_df, self.enum_df
        except Exception as e:
            print(f"加载数据时发生错误: {e}")
            return None, None

    def get_market_ticker_map(self):
        """获取市场和对应的ticker映射
        
        Returns:
            dict: 市场到ticker的映射字典
        """
        if self.trades_df is None or self.enum_df is None:
            print("请先加载交易数据和枚举数据")
            return None
            
        markets = self.trades_df['Market'].unique()
        self.market_ticker_map = {}
        for market in markets:
            ticker = self.enum_df[self.enum_df['Name'] == market]['Ticker'].iloc[0] if len(self.enum_df[self.enum_df['Name'] == market]) > 0 else None
            if ticker:
                self.market_ticker_map[market] = ticker
        return self.market_ticker_map

    @staticmethod
    def get_previous_business_day(target_date):
        """获取前一个工作日
        
        Args:
            target_date (datetime): 目标日期
            
        Returns:
            datetime: 前一个工作日
        """
        prev_day = target_date - pd.Timedelta(days=1)
        while prev_day.weekday() >= 5:  # 5是周六，6是周日
            prev_day = prev_day - pd.Timedelta(days=1)
        return prev_day

    @staticmethod
    def get_fx_rates(target_date):
        """获取汇率数据
        
        Args:
            target_date (datetime): 目标日期
            
        Returns:
            tuple: (当前汇率, 前一日汇率)
        """
        GBPUSD = yf.Ticker("GBPUSD=X")
        GBPUSD_FX_Hist = GBPUSD.history(start=(target_date - pd.Timedelta(days=5)), end=target_date)
        if not GBPUSD_FX_Hist.empty:
            return float(GBPUSD_FX_Hist['Close'].iloc[-1]), float(GBPUSD_FX_Hist['Close'].iloc[-2])
        return 1.0, 1.0

    def save_results(self, daily_pnl_result, trade_history_paths):
        """保存结果到文件
        
        Args:
            daily_pnl_result (dict): 每日盈亏结果
            trade_history_paths (list): 交易历史文件路径列表
        """
        if self.investment_dir is None:
            print("未设置investment_dir，无法保存结果")
            return
            
        daily_pnl_dir = os.path.join(self.investment_dir, 'Daily Pnl')
        os.makedirs(daily_pnl_dir, exist_ok=True)
        
        source_prefix = '_'.join(path.split('TradeHistory-')[1].split('.')[0] for path in trade_history_paths)
        pnl_file = os.path.join(daily_pnl_dir, 
                               f'daily_pnl_{source_prefix}_{daily_pnl_result["date"].strftime("%Y%m%d")}.pkl')
        
        with open(pnl_file, 'wb') as f:
            pickle.dump(daily_pnl_result, f)
        print(f"\n已保存当日盈亏数据到: {pnl_file}")

if __name__ == "__main__":
    # 测试数据加载功能
    print("测试数据加载模块")
    
    # 设置测试路径
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    investment_dir = os.path.join(os.path.dirname(base_dir), 'investment')
    trade_history_path = os.path.join(investment_dir, 'TradeHistory-SXAFI-(01-03-2017)-(02-03-2025).csv')
    enum_path = os.path.join(investment_dir, 'enum.csv')
    
    # 创建DataLoader实例
    data_loader = DataLoader(investment_dir)
    
    # 测试加载交易数据
    trades_df, enum_df = data_loader.load_trade_data([trade_history_path], enum_path)
    if trades_df is not None and enum_df is not None:
        print("成功加载交易数据")
        print(f"交易数据行数: {len(trades_df)}")
        print(f"枚举数据行数: {len(enum_df)}")
    
    # 测试获取市场ticker映射
    market_ticker_map = data_loader.get_market_ticker_map()
    if market_ticker_map:
        print("\n市场ticker映射:")
        for market, ticker in market_ticker_map.items():
            print(f"{market}: {ticker}")
    
    # 测试获取汇率
    fx_rate, fx_rate_prev = DataLoader.get_fx_rates(datetime.today())
    print(f"\n当前汇率: {fx_rate}")
    print(f"前一日汇率: {fx_rate_prev}") 