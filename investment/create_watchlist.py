"""
创建股票watch list的脚本
"""

import pickle
import os

def create_watchlist():
    """创建包含指定股票和权重的watch list"""
    # 定义股票和权重
    watchlist_weights = {
        'NFLX': 0.1,
        'WMT': 0.1,
        'TSLA': 0,
        'GOOG': 0.1,
        'AMD': 0.1,
        'CNA.L': 0.1,
        'UBER': 0.1,
        'NIO': 0,
        'NTES': 0.1,
        'NWG.L': 0.1,
        'GSPX.L': 0.1,
        'SAP': 0.1
    }
    
    # 验证权重总和为1
    total_weight = sum(watchlist_weights.values())
    if abs(total_weight - 1.0) > 0.001:
        print(f"警告：权重总和为 {total_weight:.3f}，不等于1.0")
    
    # 设置名义金额
    notional_amount = 25000
    
    # 计算每个股票的名义金额分配
    stock_allocations = {}
    for stock, weight in watchlist_weights.items():
        allocation = notional_amount * weight
        stock_allocations[stock] = {
            'weight': weight,
            'notional_allocation': allocation
        }
    
    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    watchlist_path = os.path.join(script_dir, 'watchlist.pkl')
    
    # 保存为pickle文件
    with open(watchlist_path, 'wb') as f:
        pickle.dump(stock_allocations, f)
    
    print(f"Watch list已创建，名义金额: {notional_amount}")
    print("股票分配详情:")
    print("-" * 50)
    print(f"{'股票':<10} {'权重':<8} {'分配金额':<12}")
    print("-" * 50)
    for stock, data in stock_allocations.items():
        print(f"{stock:<10} {data['weight']:<8.3f} {data['notional_allocation']:<12.2f}")
    print("-" * 50)
    print(f"文件保存位置: {watchlist_path}")
    return stock_allocations

if __name__ == "__main__":
    create_watchlist() 